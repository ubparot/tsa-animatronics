"""CUDA-graph decoding for Chatterbox Turbo's T3 token loop.

Stock T3.inference_turbo runs GPT-2 one speech token at a time from Python,
launching several hundred tiny GPU kernels per token and syncing with the CPU
twice per token. The GPU sits mostly idle: on the RTX 5080 it manages ~43
tokens/s (25/s is real time), and on a slower CPU it gets worse.

This decoder computes exactly the same thing, but records one whole token step
(attention over a static KV cache, the logits, and sampling) as a CUDA graph
and replays it, so the launch overhead is paid once per step. Measured on the
5080: 43 -> 214 tokens/s in fp32, 305 tokens/s in bf16, with first-clause
synthesis 0.9 s -> 0.37 s.

Safety:
- install() checks the graph against the stock HF model in fp32 on a
  teacher-forced token sequence before using it; on any mismatch or error the
  model is left untouched and stock decoding is used.
- bf16 is applied only after that check passes.
- Sampling settings live in GPU tensors, so the Performance Lab can change
  temperature, top-p and repetition penalty freely; a new top-k re-captures.
"""

from __future__ import annotations

import logging

import torch
import torch.nn.functional as F
from transformers.generation.logits_process import (
    LogitsProcessorList,
    RepetitionPenaltyLogitsProcessor,
    TemperatureLogitsWarper,
    TopKLogitsWarper,
    TopPLogitsWarper,
)


LOGGER = logging.getLogger(__name__)


class T3GraphDecoder:
    """Drop-in replacement for T3.inference_turbo (batch 1, CUDA only)."""

    # Replay this many steps between host-side checks for the stop token; up
    # to this many extra tokens are computed and discarded after it.
    CHECK_EVERY = 8
    # One graph per attention length, so early tokens do not attend over (and
    # read) the whole static cache. The smallest bucket that fits is replayed.
    BUCKETS = (256, 384, 512, 768, 1024, 1536)

    def __init__(self, t3: torch.nn.Module) -> None:
        self.t3 = t3
        tf = t3.tfmr
        self.blocks = list(tf.h)
        self.ln_f = tf.ln_f
        self.C = t3.cfg.hidden_size
        self.H = t3.cfg.n_head
        self.D = self.C // self.H
        self.max_len = self.BUCKETS[-1]
        self.stop = t3.hp.stop_speech_token
        self.start = t3.hp.start_speech_token
        device = tf.wpe.weight.device
        vocab = t3.speech_head.out_features
        self.positions = torch.arange(self.max_len, device=device)
        self.cur_token = torch.zeros(1, 1, dtype=torch.long, device=device)
        self.pos = torch.zeros(1, dtype=torch.long, device=device)
        self.step_idx = torch.zeros(1, dtype=torch.long, device=device)
        self.seen = torch.zeros(vocab, dtype=torch.bool, device=device)
        self.out_tokens = torch.full((self.max_len + self.CHECK_EVERY,), self.stop, dtype=torch.long, device=device)
        self.last_logits = torch.zeros(1, vocab, dtype=torch.float32, device=device)
        self.temperature = torch.ones(1, device=device)
        self.top_p = torch.ones(1, device=device)
        self.repetition_penalty = torch.ones(1, device=device)
        self.top_k: int | None = None
        self.graphs: dict[int, torch.cuda.CUDAGraph] = {}
        self._allocate_cache()

    @property
    def dtype(self) -> torch.dtype:
        return self.t3.tfmr.wpe.weight.dtype

    def _allocate_cache(self) -> None:
        weight = self.t3.tfmr.wpe.weight
        shape = (len(self.blocks), 1, self.H, self.max_len, self.D)
        self.k_cache = torch.zeros(shape, dtype=weight.dtype, device=weight.device)
        self.v_cache = torch.zeros_like(self.k_cache)

    def to_bf16(self) -> None:
        """Run the transformer in bfloat16 (~40% faster than fp32 decoding)."""
        self.t3.tfmr.to(torch.bfloat16)
        self.t3.speech_emb.to(torch.bfloat16)
        self.t3.speech_head.to(torch.bfloat16)
        self.graphs.clear()
        self._allocate_cache()

    # ---- one decode step (captured) --------------------------------------------
    def _step(self, length: int) -> None:
        t3 = self.t3
        wpe = t3.tfmr.wpe.weight
        x = t3.speech_emb(self.cur_token) + wpe.index_select(0, self.pos).view(1, 1, self.C)
        mask = (self.positions[:length] <= self.pos).view(1, 1, 1, length)
        for i, block in enumerate(self.blocks):
            q, k, v = block.attn.c_attn(block.ln_1(x)).split(self.C, dim=2)
            q = q.view(1, 1, self.H, self.D).transpose(1, 2)
            self.k_cache[i].index_copy_(2, self.pos, k.view(1, 1, self.H, self.D).transpose(1, 2))
            self.v_cache[i].index_copy_(2, self.pos, v.view(1, 1, self.H, self.D).transpose(1, 2))
            attended = F.scaled_dot_product_attention(
                q, self.k_cache[i][:, :, :length], self.v_cache[i][:, :, :length], attn_mask=mask
            )
            x = x + block.attn.c_proj(attended.transpose(1, 2).reshape(1, 1, self.C))
            x = x + block.mlp(block.ln_2(x))
        logits = t3.speech_head(self.ln_f(x))[:, -1, :].float()
        self.last_logits.copy_(logits)
        # Same processors, same order as inference_turbo: temperature, top-k,
        # top-p, repetition penalty. Each is an identity at its neutral value.
        logits = logits / self.temperature
        kth = torch.topk(logits, self.top_k).values[..., -1:]
        logits = logits.masked_fill(logits < kth, float("-inf"))
        sorted_logits, sorted_index = torch.sort(logits, descending=False)
        remove_sorted = sorted_logits.softmax(dim=-1).cumsum(dim=-1) <= (1 - self.top_p)
        remove_sorted[..., -1:] = False
        logits = logits.masked_fill(remove_sorted.scatter(1, sorted_index, remove_sorted), float("-inf"))
        penalized = torch.where(logits < 0, logits * self.repetition_penalty, logits / self.repetition_penalty)
        logits = torch.where(self.seen.view(1, -1), penalized, logits)
        probs = logits.softmax(dim=-1)
        # Exponential-race sampling draws from the same distribution as
        # torch.multinomial, and unlike it is safe inside a CUDA graph.
        token = (probs / torch.empty_like(probs).exponential_()).argmax(dim=-1, keepdim=True)
        self.seen.index_fill_(0, token.view(1), True)
        self.out_tokens.index_copy_(0, self.step_idx, token.view(1))
        self.cur_token.copy_(token)
        self.pos.add_(1)
        self.step_idx.add_(1)

    @torch.inference_mode()
    def capture(self, top_k: int) -> None:
        self.top_k = min(top_k, self.t3.speech_head.out_features)
        self.graphs.clear()
        # Warm-up and capture draw random numbers; restore the generator so a
        # seeded generation that triggers a re-capture still repeats exactly.
        rng_state = torch.cuda.get_rng_state()
        try:
            self._capture_buckets()
        finally:
            torch.cuda.set_rng_state(rng_state)

    def _capture_buckets(self) -> None:
        # Warm-up writes scratch values at positions 0-2; prompts are copied in
        # after capture, so this never touches a real cache entry.
        self.pos.zero_()
        self.step_idx.zero_()
        stream = torch.cuda.Stream()
        stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(3):
                self._step(self.BUCKETS[0])
        torch.cuda.current_stream().wait_stream(stream)
        pool = None
        for length in self.BUCKETS:
            graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph, pool=pool):
                self._step(length)
            pool = graph.pool()
            self.graphs[length] = graph

    def _prefill(self, t3_cond, text_tokens: torch.Tensor) -> tuple[torch.Tensor, int, torch.Tensor]:
        """Run the prompt through the stock model and copy its KV cache in."""
        t3 = self.t3
        start_token = self.start * torch.ones_like(text_tokens[:, :1])
        embeds, _ = t3.prepare_input_embeds(
            t3_cond=t3_cond, text_tokens=text_tokens, speech_tokens=start_token, cfg_weight=0.0
        )
        out = t3.tfmr(inputs_embeds=embeds.to(self.dtype), use_cache=True)
        prompt_len = embeds.size(1)
        if prompt_len + self.CHECK_EVERY >= self.max_len:
            raise ValueError(f"prompt of {prompt_len} tokens is too long for the static cache")
        for i, layer in enumerate(out.past_key_values.layers):
            self.k_cache[i, :, :, :prompt_len].copy_(layer.keys)
            self.v_cache[i, :, :, :prompt_len].copy_(layer.values)
        logits = t3.speech_head(out[0][:, -1:]).float()
        return start_token, prompt_len, logits[:, -1, :]

    @torch.inference_mode()
    def inference_turbo(
        self,
        t3_cond,
        text_tokens: torch.Tensor,
        temperature: float = 0.8,
        top_k: int = 1000,
        top_p: float = 0.95,
        repetition_penalty: float = 1.2,
        max_gen_len: int = 1000,
    ) -> torch.Tensor:
        if self.top_k != min(top_k, self.t3.speech_head.out_features) or not self.graphs:
            self.capture(top_k)
        self.temperature.fill_(temperature if temperature > 0 else 1.0)
        self.top_p.fill_(top_p)
        self.repetition_penalty.fill_(repetition_penalty)

        start_token, prompt_len, logits = self._prefill(t3_cond, text_tokens)
        # The first token uses the stock processors, exactly as inference_turbo does.
        processors = LogitsProcessorList()
        if temperature > 0 and temperature != 1.0:
            processors.append(TemperatureLogitsWarper(temperature))
        if top_k > 0:
            processors.append(TopKLogitsWarper(top_k))
        if top_p < 1.0:
            processors.append(TopPLogitsWarper(top_p))
        if repetition_penalty != 1.0:
            processors.append(RepetitionPenaltyLogitsProcessor(repetition_penalty))
        first = torch.multinomial(F.softmax(processors(start_token, logits), dim=-1), num_samples=1)

        tokens: list[int] = []
        if int(first) != self.stop:
            tokens.append(int(first))
            self.seen.zero_()
            self.seen.index_fill_(0, first.view(1), True)
            self.cur_token.copy_(first)
            self.pos.fill_(prompt_len)
            self.step_idx.fill_(0)
            limit = min(max_gen_len, self.max_len - prompt_len - self.CHECK_EVERY - 1)
            done = 0
            while done < limit:
                needed = prompt_len + done + self.CHECK_EVERY + 1
                graph = self.graphs[min(length for length in self.BUCKETS if length >= needed)]
                for _ in range(self.CHECK_EVERY):
                    graph.replay()
                batch = self.out_tokens[done:done + self.CHECK_EVERY].tolist()
                done += self.CHECK_EVERY
                if self.stop in batch:
                    tokens.extend(batch[: batch.index(self.stop)])
                    break
                tokens.extend(batch)
        return torch.tensor([tokens], dtype=torch.long, device=text_tokens.device)

    @torch.inference_mode()
    def check_against_stock(self, t3_cond, text_tokens: torch.Tensor, steps: int = 12) -> float:
        """Max relative logit difference vs the stock HF model, teacher-forced."""
        t3 = self.t3
        torch.manual_seed(0)
        sequence = torch.randint(0, self.start, (steps,)).tolist()
        start_token = self.start * torch.ones_like(text_tokens[:, :1])
        embeds, _ = t3.prepare_input_embeds(
            t3_cond=t3_cond, text_tokens=text_tokens, speech_tokens=start_token, cfg_weight=0.0
        )
        past = t3.tfmr(inputs_embeds=embeds.to(self.dtype), use_cache=True).past_key_values
        reference = []
        for token in sequence:
            embed = t3.speech_emb(torch.tensor([[token]], device=text_tokens.device))
            out = t3.tfmr(inputs_embeds=embed, past_key_values=past, use_cache=True)
            past = out.past_key_values
            reference.append(t3.speech_head(out[0])[:, -1, :].float())

        _start, prompt_len, _logits = self._prefill(t3_cond, text_tokens)
        self.pos.fill_(prompt_len)
        self.step_idx.fill_(0)
        graph = self.graphs[min(length for length in self.BUCKETS if length >= prompt_len + steps + 1)]
        worst = 0.0
        for token, expected in zip(sequence, reference):
            self.cur_token.fill_(token)
            graph.replay()
            difference = (self.last_logits - expected).abs().max() / expected.abs().max()
            worst = max(worst, float(difference))
        return worst


def install(model, bf16: bool = True, tolerance: float = 1e-3) -> T3GraphDecoder | None:
    """Swap a ChatterboxTurboTTS model onto graph decoding; None if not possible.

    model must already have its voice conditionals prepared.
    """
    t3 = model.t3
    if not torch.cuda.is_available() or next(t3.parameters()).device.type != "cuda":
        return None
    if not getattr(t3, "is_gpt", False):
        return None
    try:
        decoder = T3GraphDecoder(t3)
        decoder.capture(1000)
        text_tokens = model.tokenizer("A pulley lifts heavy things.", return_tensors="pt").input_ids.to("cuda")
        difference = decoder.check_against_stock(model.conds.t3, text_tokens)
        if difference > tolerance:
            LOGGER.warning("T3 CUDA graph differs from stock (%.2e); using stock decoding.", difference)
            return None
        if bf16:
            decoder.to_bf16()
            decoder.capture(1000)
    except Exception as exc:  # any failure leaves the stock model in charge
        LOGGER.warning("T3 CUDA graph unavailable (%s); using stock decoding.", exc)
        if next(t3.tfmr.parameters()).dtype != torch.float32:
            t3.tfmr.float()
            t3.speech_emb.float()
            t3.speech_head.float()
        return None
    t3.inference_turbo = decoder.inference_turbo
    return decoder

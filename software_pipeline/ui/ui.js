const elements = {
  status: document.querySelector('#system-status'),
  microphone: document.querySelector('#microphone-label'),
  record: document.querySelector('#record-button'),
  text: document.querySelector('#text-question'),
  sendText: document.querySelector('#text-button'),
  model: document.querySelector('#model-mode'),
  title: document.querySelector('#response-title'),
  transcript: document.querySelector('#transcript'),
  spoken: document.querySelector('#spoken-text'),
  source: document.querySelector('#source-label'),
  helper: document.querySelector('#helper-text'),
  responsePanel: document.querySelector('.response-panel'),
  audio: document.querySelector('#response-audio'),
  truth: document.querySelector('#truth-badge'),
  nose: document.querySelector('#nose'),
  noseValue: document.querySelector('#nose-value'),
  motionList: document.querySelector('#motion-list'),
  suggestions: [...document.querySelectorAll('[data-question]')],
};

const tagClass = { TRUTH: 'truth', LIE: 'lie', CONFESSION: 'confession' };

function selectedOutcome() {
  return document.querySelector('input[name="outcome"]:checked').value || null;
}

function setBusy(busy, action = '') {
  elements.record.disabled = busy;
  elements.sendText.disabled = busy;
  elements.record.classList.toggle('recording', busy && action === 'recording');
  if (busy) {
    elements.title.textContent = action === 'recording' ? 'Listening…' : 'Pinocchio is thinking…';
    elements.helper.textContent = action === 'recording'
      ? 'Speak clearly, then pause. Recording stops automatically.'
      : 'Checking the response and preparing the local voice.';
  }
}

function showError(message) {
  elements.title.textContent = 'The workshop needs attention';
  elements.helper.textContent = message;
  elements.responsePanel.classList.add('fallback');
}

function showResult(result) {
  const { packet } = result;
  const tag = packet.truth_tag;
  const noseMotion = packet.motion.find((item) => item.axis === 'nose');
  const nosePosition = Math.round((noseMotion?.position ?? 0) * 100);

  elements.responsePanel.classList.toggle('fallback', result.fallback);
  elements.title.textContent = result.fallback ? 'Please repeat the question' : 'Pinocchio responds';
  elements.transcript.textContent = result.transcript || 'No clear speech was detected.';
  elements.spoken.textContent = packet.spoken_text;
  const modelLabel = result.model === 'pinocchio-fast' ? 'FAST 1.5B' : 'LARGE 3B';
  elements.source.textContent = `${result.source.toUpperCase()} · ${modelLabel}`;
  const timing = result.timings || {};
  const timingText = [
    timing.listen ? `listen ${timing.listen}s` : '',
    timing.transcribe ? `speech ${timing.transcribe}s` : '',
    timing.ai ? `AI ${timing.ai}s` : '',
    timing.firstAudio ? `first audio ${timing.firstAudio}s` : '',
    timing.gaps ? `gaps ${timing.gaps}s` : '',
    timing.voice ? `voice ${timing.voice}s` : '',
  ].filter(Boolean).join(' · ');
  elements.helper.textContent = result.error || `Validated local show packet · ${timingText || `next state: ${packet.next_state}`}`;
  elements.truth.textContent = tag;
  elements.truth.className = `truth-badge ${tagClass[tag] || 'neutral'}`;
  elements.nose.style.width = `${1.5 + nosePosition * 0.105}rem`;
  elements.noseValue.textContent = `${nosePosition}%`;
  elements.motionList.replaceChildren(...packet.motion.map((item) => {
    const chip = document.createElement('span');
    chip.className = 'motion-chip';
    const actuator = document.createElement('strong');
    actuator.textContent = item.axis;
    chip.append(actuator, document.createTextNode(` ${Math.round(item.position * 100)}% · ${item.duration_ms}ms`));
    return chip;
  }));
  elements.audio.hidden = false;
  elements.audio.src = result.audioUrl;
  // Streamed replies were already spoken on the show PC; keep them for replay only.
  if (!result.streamed) {
    elements.audio.play().catch(() => {});
  }
}

async function submit(path, payload, action) {
  setBusy(true, action);
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The local pipeline could not complete this turn.');
    showResult(data);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

elements.record.addEventListener('click', () => submit('/api/record', {
  forceTag: selectedOutcome(),
  model: elements.model.value,
}, 'recording'));
elements.sendText.addEventListener('click', () => {
  const text = elements.text.value.trim();
  if (!text) return showError('Type a question or use Record question.');
  submit('/api/text', { text, forceTag: selectedOutcome(), model: elements.model.value }, 'thinking');
});
elements.text.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') elements.sendText.click();
});
elements.suggestions.forEach((button) => {
  button.addEventListener('click', () => {
    elements.text.value = button.dataset.question;
    elements.text.focus();
    elements.text.setSelectionRange(elements.text.value.length, elements.text.value.length);
  });
});

async function loadStatus() {
  try {
    const status = await (await fetch('/api/status')).json();
    elements.microphone.textContent = `Input ${status.microphone ?? 'default'} · ${status.speechRecognition}${status.voice ? ` · ${status.voice}` : ''}`;
    elements.status.className = `system-status ${status.ready ? 'ready' : 'error'}`;
    elements.status.lastElementChild.textContent = status.ready ? `Local AI ready · ${status.model}` : 'Local system unavailable';
    if (status.lastError) showError(status.lastError);
  } catch {
    elements.status.className = 'system-status error';
    elements.status.lastElementChild.textContent = 'Cannot reach local system';
  }
}

loadStatus();

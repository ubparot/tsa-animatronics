const elements = {
  saveState: document.querySelector('#save-state'),
  progressCopy: document.querySelector('#progress-copy'),
  progressPercent: document.querySelector('#progress-percent'),
  progressFill: document.querySelector('#progress-fill'),
  lineCard: document.querySelector('#line-card'),
  lineNumber: document.querySelector('#line-number'),
  lineText: document.querySelector('#line-text'),
  likert: document.querySelector('#likert'),
  ratingButtons: document.querySelector('#rating-buttons'),
  previous: document.querySelector('#previous-button'),
  skip: document.querySelector('#skip-button'),
  ratedCount: document.querySelector('#rated-count'),
  ratingAverage: document.querySelector('#rating-average'),
  modelStatus: document.querySelector('#model-status'),
  train: document.querySelector('#train-button'),
  insights: document.querySelector('#insights'),
  favoriteDevices: document.querySelector('#favorite-devices'),
  modelNote: document.querySelector('#model-note'),
  modelExplanation: document.querySelector('#model-explanation'),
  newProfile: document.querySelector('#new-profile-button'),
  toast: document.querySelector('#toast'),
};

const state = {
  experiment: null,
  raterId: '',
  order: [],
  ratings: new Map(),
  cursor: 0,
  history: [],
  shownAt: 0,
  busy: false,
};

function profileId() {
  let value = localStorage.getItem('pinocchioHumorRaterV1');
  if (!value) {
    value = `rater_${crypto.randomUUID().replaceAll('-', '')}`;
    localStorage.setItem('pinocchioHumorRaterV1', value);
  }
  return value;
}

function hashSeed(text) {
  let hash = 2166136261;
  for (const character of text) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seed) {
  let value = seed || 1;
  return () => {
    value += 0x6D2B79F5;
    let output = value;
    output = Math.imul(output ^ (output >>> 15), output | 1);
    output ^= output + Math.imul(output ^ (output >>> 7), output | 61);
    return ((output ^ (output >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffledLines(lines, seedText) {
  const result = [...lines];
  const random = seededRandom(hashSeed(seedText));
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    [result[index], result[swap]] = [result[swap], result[index]];
  }
  return result;
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle('error', error);
  elements.toast.classList.add('visible');
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => elements.toast.classList.remove('visible'), 2600);
}

function humanize(value) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function currentLine() {
  return state.order[state.cursor] || null;
}

function unratedIndex(from = 0) {
  for (let offset = 0; offset < state.order.length; offset += 1) {
    const index = (from + offset) % state.order.length;
    if (!state.ratings.has(state.order[index].id)) return index;
  }
  return state.order.length;
}

function updateSummary() {
  const count = state.ratings.size;
  const total = state.order.length || 72;
  const percent = Math.round((count / total) * 100);
  const values = [...state.ratings.values()];
  elements.ratedCount.textContent = count;
  elements.ratedCount.nextElementSibling.textContent = `/ ${total} rated`;
  elements.ratingAverage.textContent = values.length
    ? `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)} / 7`
    : '—';
  elements.progressCopy.textContent = count === total ? 'Rating set complete' : `${count} of ${total} lines rated`;
  elements.progressPercent.textContent = `${percent}%`;
  elements.progressFill.style.width = `${percent}%`;
  const ready = count >= state.experiment.minimumRatings;
  elements.train.disabled = !ready || state.busy;
  elements.train.textContent = ready ? `Train with ${count} ratings` : `Train after ${state.experiment.minimumRatings} ratings`;
  if (!elements.insights.hidden) elements.modelStatus.textContent = 'Trained';
  else elements.modelStatus.textContent = ready ? 'Ready to train' : `Needs ${state.experiment.minimumRatings - count} more`;
}

function renderLine() {
  const line = currentLine();
  updateSummary();
  elements.previous.disabled = state.history.length === 0 || state.busy;
  if (!line) {
    elements.lineNumber.textContent = 'COMPLETE';
    elements.lineText.textContent = 'You rated the whole set. That is enough signal to find real patterns.';
    elements.likert.disabled = true;
    elements.ratingButtons.querySelectorAll('button').forEach((button) => button.classList.remove('selected'));
    elements.skip.disabled = true;
    return;
  }
  elements.lineNumber.textContent = String(state.cursor + 1).padStart(2, '0');
  elements.lineText.textContent = line.text;
  elements.likert.disabled = state.busy;
  elements.skip.disabled = state.busy;
  const existing = state.ratings.get(line.id);
  elements.ratingButtons.querySelectorAll('button').forEach((button) => {
    button.classList.toggle('selected', Number(button.dataset.rating) === existing);
  });
  state.shownAt = performance.now();
  elements.lineCard.animate(
    [{ opacity: 0.35, transform: 'translateY(7px)' }, { opacity: 1, transform: 'translateY(0)' }],
    { duration: 220, easing: 'ease-out' },
  );
}

function advance() {
  if (state.cursor < state.order.length) state.history.push(state.cursor);
  state.cursor = unratedIndex(state.cursor + 1);
  renderLine();
}

async function rate(value) {
  const line = currentLine();
  if (!line || state.busy) return;
  const elapsedMs = Math.round(performance.now() - state.shownAt);
  state.busy = true;
  elements.saveState.classList.add('saving');
  elements.saveState.lastChild.textContent = ' Saving…';
  renderLine();
  try {
    const response = await fetch('/api/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rater_id: state.raterId,
        line_id: line.id,
        rating: value,
        elapsed_ms: elapsedMs,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The rating could not be saved.');
    state.ratings.set(line.id, value);
    elements.saveState.classList.remove('saving');
    elements.saveState.lastChild.textContent = ' Saved locally';
    advance();
  } catch (error) {
    showToast(error.message, true);
    elements.saveState.classList.remove('saving');
    elements.saveState.lastChild.textContent = ' Save failed';
  } finally {
    state.busy = false;
    renderLine();
  }
}

function buildScale() {
  elements.ratingButtons.replaceChildren();
  for (let rating = 1; rating <= 7; rating += 1) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.rating = rating;
    button.setAttribute('aria-label', `${rating}: ${state.experiment.scale.anchors[rating]}`);
    const number = document.createElement('strong');
    number.textContent = rating;
    const label = document.createElement('span');
    label.textContent = state.experiment.scale.anchors[rating];
    button.append(number, label);
    button.addEventListener('click', () => rate(rating));
    elements.ratingButtons.append(button);
  }
}

function showModel(summary) {
  elements.insights.hidden = false;
  elements.favoriteDevices.replaceChildren(...summary.favorite_devices.slice(0, 3).map((item) => {
    const tag = document.createElement('span');
    tag.textContent = humanize(item.name);
    tag.title = `${item.mean.toFixed(1)}/7 across ${item.count} rated line${item.count === 1 ? '' : 's'}`;
    return tag;
  }));
  const validation = summary.cross_validation;
  elements.modelNote.textContent = validation
    ? `Trained on ${summary.training_examples} judgments · validation error about ${validation.mean_absolute_error.toFixed(1)} scale points.`
    : `Trained on ${summary.training_examples} judgments. Rate 20+ lines to unlock a validation estimate.`;
  elements.modelExplanation.textContent = 'The preference file and a ready-to-use writing prompt were saved locally.';
  elements.modelStatus.textContent = 'Trained';
}

async function train() {
  if (state.busy) return;
  state.busy = true;
  elements.train.disabled = true;
  elements.train.textContent = 'Finding your patterns…';
  try {
    const response = await fetch('/api/train', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Training failed.');
    showModel(result.summary);
    showToast('Preference model trained locally.');
  } catch (error) {
    showToast(error.message, true);
  } finally {
    state.busy = false;
    updateSummary();
  }
}

async function start() {
  try {
    state.raterId = profileId();
    const [experimentResponse, ratingsResponse, modelResponse] = await Promise.all([
      fetch('/api/experiment'),
      fetch(`/api/ratings?rater_id=${encodeURIComponent(state.raterId)}`),
      fetch('/api/model'),
    ]);
    if (!experimentResponse.ok || !ratingsResponse.ok || !modelResponse.ok) throw new Error('The local experiment could not be loaded.');
    state.experiment = await experimentResponse.json();
    const saved = await ratingsResponse.json();
    const model = await modelResponse.json();
    state.ratings = new Map(saved.ratings.map((record) => [record.line_id, record.rating]));
    state.order = shuffledLines(state.experiment.lines, state.raterId);
    state.cursor = unratedIndex(0);
    buildScale();
    if (model.trained) showModel(model.summary);
    renderLine();
  } catch (error) {
    elements.lineText.textContent = error.message;
    showToast(error.message, true);
  }
}

elements.previous.addEventListener('click', () => {
  if (!state.history.length || state.busy) return;
  state.cursor = state.history.pop();
  renderLine();
});
elements.skip.addEventListener('click', () => {
  if (!currentLine() || state.busy) return;
  state.history.push(state.cursor);
  state.cursor = (state.cursor + 1) % state.order.length;
  renderLine();
});
elements.train.addEventListener('click', train);
elements.newProfile.addEventListener('click', () => {
  if (!confirm('Start a separate profile? Existing ratings stay saved and will still contribute to the model.')) return;
  localStorage.removeItem('pinocchioHumorRaterV1');
  location.reload();
});
document.addEventListener('keydown', (event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
  if (/^[1-7]$/.test(event.key)) rate(Number(event.key));
  if (event.key.toLowerCase() === 's') elements.skip.click();
});

start();

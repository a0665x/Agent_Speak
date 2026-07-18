"use strict";

const MAX_RECORDING_SECONDS = 30;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;

const elements = {
  status: document.querySelector("#connection-status"), statusLabel: document.querySelector("#status-label"),
  record: document.querySelector("#record-button"), recordLabel: document.querySelector("#record-label"),
  upload: document.querySelector("#audio-upload"), uploadLabel: document.querySelector("#audio-upload-label"), error: document.querySelector("#action-error"),
  turnState: document.querySelector("#turn-state"), pipeline: document.querySelector("#pipeline-list"),
  transcript: document.querySelector("#transcript"), response: document.querySelector("#agent-response"),
  player: document.querySelector("#tts-player"), latency: document.querySelector("#total-latency"),
  capabilities: document.querySelector("#capability-list"), speakerForm: document.querySelector("#speaker-form"),
  speakerName: document.querySelector("#speaker-name"), speakers: document.querySelector("#speaker-list"),
  enroll: document.querySelector("#enroll-button"), match: document.querySelector("#match-button"),
  rename: document.querySelector("#rename-button"), remove: document.querySelector("#delete-button"), speakerResult: document.querySelector("#speaker-result")
};

const state = { sessionId: null, socket: null, recorder: null, stream: null, chunks: [], lastWav: null, selectedSpeaker: null, recording: false, processing: false, recordingTimer: null, lastSequence: 0, reconnectAttempts: 0, reconnectTimer: null };

function clearChildren(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function showError(message) { elements.error.textContent = message; elements.error.hidden = !message; }
function errorMessage(payload, fallback) { return payload && payload.error ? `${payload.error.message}. ${payload.error.retryable ? "Please try again." : "Check the input and retry."}` : fallback; }
function validateAudioSize(blob) { if (blob.size > MAX_AUDIO_BYTES) throw new Error("Audio exceeds the 8 MiB upload limit."); }
function setCaptureDisabled(disabled) {
  elements.record.disabled = disabled;
  elements.upload.disabled = disabled;
  elements.uploadLabel.setAttribute("aria-disabled", String(disabled));
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(errorMessage(payload, `Request failed (${response.status})`));
  return payload;
}

function setConnection(kind, label) { elements.status.className = `status-pill ${kind}`; elements.statusLabel.textContent = label; }
function setTurnState(label) { elements.turnState.textContent = label; }
function resetPipeline() {
  elements.pipeline.querySelectorAll("li").forEach((item) => { item.removeAttribute("data-state"); item.querySelector("output").textContent = "Waiting"; });
  elements.latency.textContent = "—";
}

function applyEvent(event) {
  if (event.sequence <= state.lastSequence) return;
  state.lastSequence = event.sequence;
  if (event.stage) {
    const item = elements.pipeline.querySelector(`[data-stage="${event.stage}"]`);
    if (item) {
      const status = event.type.endsWith("started") ? "running" : event.type.endsWith("failed") ? "failed" : "complete";
      item.dataset.state = status;
      item.querySelector("output").textContent = event.elapsed_ms === null ? (status === "running" ? "Running" : status) : `${event.elapsed_ms.toFixed(1)} ms`;
    }
  }
  if (event.type === "pipeline.started") setTurnState("Processing locally");
  if (event.type === "pipeline.completed") setTurnState("Turn completed");
  if (event.type === "pipeline.failed") setTurnState(`Failed at ${event.stage || "pipeline"}`);
}

function connectEvents() {
  if (state.reconnectTimer) window.clearTimeout(state.reconnectTimer);
  if (state.socket) state.socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${scheme}://${location.host}/api/v1/sessions/${state.sessionId}/events`);
  state.socket.addEventListener("open", () => { state.reconnectAttempts = 0; setConnection("ready", "Ready · local"); });
  state.socket.addEventListener("message", (message) => applyEvent(JSON.parse(message.data)));
  state.socket.addEventListener("close", () => {
    if (!state.sessionId) return;
    setConnection("", "Event stream reconnecting");
    const delay = Math.min(10000, 500 * (2 ** state.reconnectAttempts));
    state.reconnectAttempts += 1;
    state.reconnectTimer = setTimeout(connectEvents, delay);
  });
  state.socket.addEventListener("error", () => setConnection("error", "Event stream unavailable"));
}

function encodeWav(audioBuffer) {
  const channels = audioBuffer.numberOfChannels;
  const length = audioBuffer.length;
  const mono = new Float32Array(length);
  for (let channel = 0; channel < channels; channel += 1) {
    const source = audioBuffer.getChannelData(channel);
    for (let index = 0; index < length; index += 1) mono[index] += source[index] / channels;
  }
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const write = (offset, value) => { for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index)); };
  write(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, audioBuffer.sampleRate, true); view.setUint32(28, audioBuffer.sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, length * 2, true);
  for (let index = 0; index < length; index += 1) {
    const sample = Math.max(-1, Math.min(1, mono[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function convertToWav(blob) {
  validateAudioSize(blob);
  if (blob.type === "audio/wav" || blob.name?.toLowerCase().endsWith(".wav")) return new Blob([await blob.arrayBuffer()], { type: "audio/wav" });
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const context = new AudioContextClass();
  try { return encodeWav(await context.decodeAudioData(await blob.arrayBuffer())); }
  finally { await context.close(); }
}

function updateSpeakerActions() {
  elements.enroll.disabled = !(state.selectedSpeaker && state.lastWav);
  elements.match.disabled = !state.lastWav;
  elements.remove.disabled = !state.selectedSpeaker;
  elements.rename.disabled = !state.selectedSpeaker;
}

async function submitTurn(wav) {
  validateAudioSize(wav);
  state.lastWav = wav; updateSpeakerActions(); resetPipeline(); showError(""); setTurnState("Uploading bounded WAV");
  state.processing = true; setCaptureDisabled(true);
  try {
    const result = await request(`/api/v1/sessions/${state.sessionId}/turns`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: wav });
    elements.transcript.textContent = result.corrected_text || result.transcript;
    elements.transcript.className = "";
    elements.response.textContent = result.response;
    elements.response.className = "";
    elements.player.src = result.audio_url; elements.player.hidden = false;
    const total = Object.values(result.latencies_ms).reduce((sum, value) => sum + value, 0);
    elements.latency.textContent = `${total.toFixed(1)} ms`;
    setTurnState("Turn completed");
  } catch (error) { showError(`${error.message} Record clear speech for under 30 seconds.`); setTurnState("Turn needs attention"); }
  finally { state.processing = false; setCaptureDisabled(false); }
}

async function stopRecording() {
  if (state.recorder && state.recorder.state !== "inactive") state.recorder.stop();
}

async function toggleRecording() {
  showError("");
  if (state.processing) return;
  if (state.recording) { await stopRecording(); return; }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true }, video: false });
    state.chunks = [];
    state.recorder = new MediaRecorder(state.stream);
    state.recorder.addEventListener("dataavailable", (event) => { if (event.data.size) state.chunks.push(event.data); });
    state.recorder.addEventListener("stop", async () => {
      if (state.recordingTimer) clearTimeout(state.recordingTimer);
      state.recordingTimer = null;
      state.recording = false; elements.record.classList.remove("recording"); elements.recordLabel.textContent = "Start recording";
      state.stream.getTracks().forEach((track) => track.stop());
      setCaptureDisabled(true);
      try {
        const wav = await convertToWav(new Blob(state.chunks, { type: state.recorder.mimeType }));
        validateAudioSize(wav);
        await submitTurn(wav);
      }
      catch (error) { showError(`${error.message} Try uploading a PCM WAV file instead.`); setCaptureDisabled(false); }
    });
    state.recorder.start(); state.recording = true; elements.upload.disabled = true; elements.record.classList.add("recording"); elements.recordLabel.textContent = "Stop & process"; setTurnState("Recording · auto-stops at 30 seconds");
    state.recordingTimer = setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000);
  } catch (error) { showError(`Microphone access failed: ${error.message}. Allow permission or upload audio.`); }
}

function renderCapabilities(payload) {
  clearChildren(elements.capabilities); elements.capabilities.setAttribute("aria-busy", "false");
  payload.providers.forEach((provider) => {
    const item = element("li"); const name = element("strong", provider.stage); const badge = element("span", provider.development ? "Development" : "Functional", "provider-badge");
    const detail = element("span", provider.name); const limitation = element("small", provider.limitations.join(" ") || "Local deterministic signal analysis.");
    item.append(name, badge, detail, limitation); elements.capabilities.append(item);
  });
}

function renderSpeakers(payload) {
  clearChildren(elements.speakers);
  if (!payload.speakers.length) elements.speakers.append(element("li", "No profiles yet. Add one to enroll the last turn.", "empty-copy"));
  payload.speakers.forEach((speaker) => {
    const item = element("li"); const button = element("button"); button.type = "button"; button.setAttribute("aria-pressed", String(state.selectedSpeaker === speaker.id));
    button.append(element("strong", speaker.name), element("small", `${speaker.sample_count} enrolled sample${speaker.sample_count === 1 ? "" : "s"}`));
    button.addEventListener("click", () => { state.selectedSpeaker = speaker.id; renderSpeakers(payload); updateSpeakerActions(); elements.speakerResult.textContent = `${speaker.name} selected.`; });
    item.append(button); elements.speakers.append(item);
  });
}

async function refreshSpeakers() { renderSpeakers(await request("/api/v1/speakers")); }

async function initialize() {
  try {
    const [health, capabilities, session] = await Promise.all([request("/api/v1/health"), request("/api/v1/capabilities"), request("/api/v1/sessions", { method: "POST" })]);
    if (health.status !== "ok") throw new Error("Service is not healthy");
    state.sessionId = session.id; renderCapabilities(capabilities); await refreshSpeakers(); connectEvents(); setCaptureDisabled(false);
  } catch (error) { setConnection("error", "Service unavailable"); showError(`${error.message}. Start the local service and reload.`); }
}

elements.record.addEventListener("click", toggleRecording);
elements.upload.addEventListener("change", async () => {
  const file = elements.upload.files[0]; if (!file || state.processing) return;
  setCaptureDisabled(true);
  try {
    validateAudioSize(file);
    const wav = await convertToWav(file);
    validateAudioSize(wav);
    await submitTurn(wav);
  } catch (error) { showError(`${error.message} Choose a browser-readable audio file.`); setCaptureDisabled(false); }
  finally { elements.upload.value = ""; }
});
elements.speakerForm.addEventListener("submit", async (event) => { event.preventDefault(); try { await request("/api/v1/speakers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: elements.speakerName.value }) }); elements.speakerName.value = ""; await refreshSpeakers(); elements.speakerResult.textContent = "Speaker profile created."; } catch (error) { elements.speakerResult.textContent = error.message; } });
elements.enroll.addEventListener("click", async () => { try { const result = await request(`/api/v1/speakers/${state.selectedSpeaker}/samples`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: state.lastWav }); await refreshSpeakers(); elements.speakerResult.textContent = `${result.speaker.name} enrolled. This is not authentication.`; } catch (error) { elements.speakerResult.textContent = error.message; } });
elements.match.addEventListener("click", async () => { try { const result = await request("/api/v1/speakers/match", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: state.lastWav }); elements.speakerResult.textContent = result.match ? `Closest profile: ${result.match.name} (${(result.score * 100).toFixed(1)}%). Not authentication.` : "No profile met the local convenience threshold. Not authentication."; } catch (error) { elements.speakerResult.textContent = error.message; } });
elements.rename.addEventListener("click", async () => { const name = window.prompt("New name for the selected local profile:"); if (!name) return; try { await request(`/api/v1/speakers/${state.selectedSpeaker}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, notes: "" }) }); await refreshSpeakers(); elements.speakerResult.textContent = "Speaker profile renamed."; } catch (error) { elements.speakerResult.textContent = error.message; } });
elements.remove.addEventListener("click", async () => { if (!state.selectedSpeaker || !window.confirm("Delete this local speaker profile and its private samples?")) return; try { await request(`/api/v1/speakers/${state.selectedSpeaker}`, { method: "DELETE" }); state.selectedSpeaker = null; await refreshSpeakers(); updateSpeakerActions(); elements.speakerResult.textContent = "Local profile and samples deleted."; } catch (error) { elements.speakerResult.textContent = error.message; } });

initialize();

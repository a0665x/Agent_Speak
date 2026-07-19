"use strict";

const MAX_RECORDING_SECONDS = 30;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const DEFAULT_LOCALE = "zh-TW";
const translations = {
  "zh-TW": {
    skip: "跳到語音工作台", brandAria: "Agent Speak 首頁", connecting: "連線中", localWorkspace: "本機語音工作空間",
    hero1: "說一次就好。", hero2: "看懂每個步驟。", heroCopy: "錄下一段話、查看完整處理流程；語音資料留在這台機器上。",
    beginHere: "先從這裡開始", quickStart: "3 步快速開始", quick1: "錄音或上傳", quick1Help: "按下錄音，或選擇現有音訊。",
    quick2: "觀察處理流程", quick2Help: "依序確認六個語音處理階段。", quick3: "查看文字與回覆", quick3Help: "閱讀辨識結果並播放語音回覆。",
    captureTitle: "錄音或選擇音訊", startRecording: "開始錄音", stopProcess: "停止並處理", upload: "上傳音訊",
    captureHelp: "錄音會在 30 秒後自動停止。原始及轉換後音訊皆不得超過 8 MiB；瀏覽器會先在本機轉成 16-bit PCM WAV。",
    liveExecution: "即時執行", pipelineTitle: "處理流程時間軸", pipelineHelp: "這裡會依序顯示語音如何被處理，以及每一步花費的時間。",
    waitingTurn: "等待語音", waiting: "等待中", running: "處理中", complete: "完成", failed: "失敗", processing: "正在本機處理", turnComplete: "處理完成",
    vadShort: "偵測人聲", asrShort: "語音轉文字", correctionShort: "文字校正", endpointShort: "判斷語句結束", agentShort: "產生本機回覆", ttsShort: "文字轉語音",
    turnRecord: "本次結果", conversation: "辨識文字與 Agent 回覆", resultsHelp: "完成處理後，可在這裡核對文字、回覆與語音成品。",
    transcriptTitle: "辨識文字", transcriptEmpty: "錄音完成後，辨識文字會顯示在這裡。", responseTitle: "Agent 回覆", responseEmpty: "開發版 Agent 的回覆會顯示在這裡。",
    playerAria: "合成的回覆音訊", totalLatency: "各階段總耗時", advanced: "進階功能", capabilities: "目前能力", capabilitiesHelp: "查看每個階段實際使用的提供者與限制。",
    loadingProviders: "正在載入提供者…", speakers: "說話者資料", speakersHelp: "建立本機資料，以最近一段語音進行便利辨識。", speakerNotice: "比對只供本機便利識別，不是生物辨識身分驗證。",
    newProfile: "新資料名稱", add: "新增", noProfiles: "目前沒有說話者資料。", speakerActionsAria: "已選說話者操作", enroll: "登錄上一段語音", match: "比對上一段語音",
    rename: "重新命名", delete: "刪除資料", speakerHint: "先選擇資料並錄音，才能登錄。", reference: "快速參考", glossary: "名詞小抄",
    vadDefinition: "Voice Activity Detection，判斷音訊中是否有人聲。", asrDefinition: "Automatic Speech Recognition，將語音轉為文字。", ttsDefinition: "Text-to-Speech，將 Agent 回覆轉為可播放音訊。",
    footer: "能力區會標示開發版提供者。", ready: "就緒 · 本機", reconnecting: "事件串流重新連線中", streamUnavailable: "事件串流無法使用", serviceUnavailable: "服務無法使用",
    uploadBounded: "正在上傳 WAV", recording: "錄音中 · 30 秒後自動停止", turnAttention: "這段語音需要處理", development: "開發版", functional: "可使用",
    defaultLimitation: "本機確定性訊號分析。", noProfilesLong: "尚無資料，請新增一筆以登錄上一段語音。", sample: "筆已登錄樣本", selected: "已選取。",
    profileCreated: "說話者資料已建立。", enrolled: "已登錄。這不是身分驗證。", closest: "最接近的資料", noMatch: "沒有資料達到本機便利比對門檻。這不是身分驗證。",
    promptRename: "請輸入所選本機資料的新名稱：", renamed: "說話者資料已重新命名。", confirmDelete: "刪除這筆本機說話者資料及其私人樣本？", deleted: "本機資料與樣本已刪除。",
    tryAgain: "請再試一次。", checkInput: "請檢查輸入後重試。", requestFailed: "請求失敗", tooLarge: "音訊超過 8 MiB 上傳限制。", serviceUnhealthy: "服務健康狀態異常",
    startService: "請啟動本機服務後重新載入。", recordClear: "請錄製 30 秒內的清楚語音。", tryWav: "請改為上傳 PCM WAV 檔案。", micFailed: "麥克風存取失敗", allowMic: "請允許權限或上傳音訊。", readableAudio: "請選擇瀏覽器可讀取的音訊檔案。", failedAt: "失敗階段",
    limitationAsr: "目前只回傳測試文字，尚非真正語音辨識。", limitationCorrection: "目前只處理空白與句子大小寫。", limitationEndpoint: "目前只使用標點與文字長度判斷。", limitationAgent: "目前是範本回覆，尚未串接語言模型。", limitationTts: "目前輸出合成提示音，尚非自然語音。", limitationInjected: "外部注入的提供者；限制請查看部署設定。", limitationWhisper: "本機 Faster-Whisper 語音辨識（CPU 推論）。", limitationPiper: "本機 Piper 中文語音合成。"
  },
  en: {
    skip: "Skip to voice console", brandAria: "Agent Speak home", connecting: "Connecting", localWorkspace: "Local voice workspace",
    hero1: "Say it once.", hero2: "See every stage.", heroCopy: "Capture a turn, inspect the complete pipeline, and keep voice data on this machine.",
    beginHere: "Start here", quickStart: "Quick start in 3 steps", quick1: "Record or upload", quick1Help: "Record with your microphone or choose existing audio.", quick2: "Watch the pipeline", quick2Help: "Follow the six voice processing stages.", quick3: "Read text and response", quick3Help: "Review the transcript and play the spoken response.",
    captureTitle: "Record or choose audio", startRecording: "Start recording", stopProcess: "Stop & process", upload: "Upload audio", captureHelp: "Recording auto-stops at 30 seconds. Source and converted audio must each be 8 MiB or smaller; the browser converts audio locally to 16-bit PCM WAV.",
    liveExecution: "Live execution", pipelineTitle: "Pipeline timeline", pipelineHelp: "This area shows how speech is processed in order and how long each stage takes.", waitingTurn: "Waiting for a turn", waiting: "Waiting", running: "Running", complete: "Complete", failed: "Failed", processing: "Processing locally", turnComplete: "Turn completed",
    vadShort: "Voice detection", asrShort: "Speech to text", correctionShort: "Text cleanup", endpointShort: "Turn completion", agentShort: "Local response", ttsShort: "Text to speech",
    turnRecord: "Turn record", conversation: "Transcript and Agent response", resultsHelp: "After processing, review the text, response, and audio here.", transcriptTitle: "Transcript", transcriptEmpty: "Your transcript will appear after a recorded turn.", responseTitle: "Agent response", responseEmpty: "The development Agent response will appear here.", playerAria: "Synthesized response audio", totalLatency: "Total stage latency",
    advanced: "Advanced", capabilities: "Capabilities", capabilitiesHelp: "See the active provider and limitations for each stage.", loadingProviders: "Loading providers…", speakers: "Speaker profiles", speakersHelp: "Create local profiles for convenience matching with the latest audio.", speakerNotice: "Matching is local convenience identification, not biometric authentication.",
    newProfile: "New profile name", add: "Add", noProfiles: "No speaker profiles yet.", speakerActionsAria: "Selected speaker actions", enroll: "Enroll last turn", match: "Match last turn", rename: "Rename selected", delete: "Delete profile", speakerHint: "Select a profile and record a turn to enroll.", reference: "Quick reference", glossary: "Glossary",
    vadDefinition: "Voice Activity Detection checks whether audio contains speech.", asrDefinition: "Automatic Speech Recognition turns speech into text.", ttsDefinition: "Text-to-Speech turns the Agent response into playable audio.", footer: "Development providers are labelled in capabilities.",
    ready: "Ready · local", reconnecting: "Event stream reconnecting", streamUnavailable: "Event stream unavailable", serviceUnavailable: "Service unavailable", uploadBounded: "Uploading bounded WAV", recording: "Recording · auto-stops at 30 seconds", turnAttention: "Turn needs attention", development: "Development", functional: "Functional", defaultLimitation: "Local deterministic signal analysis.",
    noProfilesLong: "No profiles yet. Add one to enroll the last turn.", sample: "enrolled sample(s)", selected: "selected.", profileCreated: "Speaker profile created.", enrolled: "enrolled. This is not authentication.", closest: "Closest profile", noMatch: "No profile met the local convenience threshold. Not authentication.", promptRename: "New name for the selected local profile:", renamed: "Speaker profile renamed.", confirmDelete: "Delete this local speaker profile and its private samples?", deleted: "Local profile and samples deleted.",
    tryAgain: "Please try again.", checkInput: "Check the input and retry.", requestFailed: "Request failed", tooLarge: "Audio exceeds the 8 MiB upload limit.", serviceUnhealthy: "Service is not healthy", startService: "Start the local service and reload.", recordClear: "Record clear speech for under 30 seconds.", tryWav: "Try uploading a PCM WAV file instead.", micFailed: "Microphone access failed", allowMic: "Allow permission or upload audio.", readableAudio: "Choose a browser-readable audio file.", failedAt: "Failed at",
    limitationAsr: "Signal-derived fixture text; not speech recognition.", limitationCorrection: "Whitespace and sentence casing only.", limitationEndpoint: "Punctuation and text-length heuristic only.", limitationAgent: "Template response; no language model inference.", limitationTts: "Synthetic tone WAV; not natural speech.", limitationInjected: "Injected provider; consult deployment configuration for model limitations.", limitationWhisper: "Local Faster-Whisper speech recognition (CPU inference).", limitationPiper: "Local Piper Mandarin speech synthesis."
  }
};
let currentLocale = DEFAULT_LOCALE;
function t(key) { return translations[currentLocale][key] || translations[DEFAULT_LOCALE][key] || key; }

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
  rename: document.querySelector("#rename-button"), remove: document.querySelector("#delete-button"), speakerResult: document.querySelector("#speaker-result"),
  language: document.querySelector("#language-toggle")
};

const state = { sessionId: null, socket: null, recorder: null, stream: null, chunks: [], lastWav: null, selectedSpeaker: null, recording: false, processing: false, recordingTimer: null, lastSequence: 0, reconnectAttempts: 0, reconnectTimer: null, capabilitiesPayload: null, speakersPayload: null, connectionKind: "", connectionKey: "connecting", turnKey: "waitingTurn", turnDetail: "", speakerResultFactory: null, actionErrorFactory: null };

function readStoredLocale() {
  try { return localStorage.getItem("agent-speak-locale"); }
  catch (_) { return null; }
}
function writeStoredLocale(locale) {
  try { localStorage.setItem("agent-speak-locale", locale); }
  catch (_) { /* Storage can be unavailable in privacy-restricted browsers. */ }
}

function setLocale(locale, persist = true) {
  currentLocale = locale === "en" ? "en" : DEFAULT_LOCALE;
  document.documentElement.lang = currentLocale === "zh-TW" ? "zh-Hant-TW" : "en";
  document.title = currentLocale === "zh-TW" ? "Agent Speak — 本機語音工作台" : "Agent Speak — Voice Console";
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel)); });
  elements.language.textContent = currentLocale === "zh-TW" ? "English" : "繁體中文";
  elements.language.setAttribute("aria-label", currentLocale === "zh-TW" ? "切換語言" : "Switch language");
  elements.language.setAttribute("aria-pressed", String(currentLocale === "en"));
  if (persist) writeStoredLocale(currentLocale);
  setConnection(state.connectionKind, state.connectionKey);
  setTurnState(state.turnKey, state.turnDetail);
  elements.recordLabel.textContent = t(state.recording ? "stopProcess" : "startRecording");
  elements.pipeline.querySelectorAll("li[data-state]").forEach((item) => {
    item.querySelector("output").textContent = item.dataset.elapsed || t(item.dataset.state);
  });
  if (state.capabilitiesPayload) renderCapabilities(state.capabilitiesPayload);
  if (state.speakersPayload) renderSpeakers(state.speakersPayload);
  if (state.speakerResultFactory) setSpeakerResult(state.speakerResultFactory);
  if (state.actionErrorFactory) showError(state.actionErrorFactory);
}

function clearChildren(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function showError(message) {
  state.actionErrorFactory = typeof message === "function" ? message : null;
  const rendered = state.actionErrorFactory ? state.actionErrorFactory() : message;
  elements.error.textContent = rendered;
  elements.error.hidden = !rendered;
}
function setSpeakerResult(message) {
  state.speakerResultFactory = typeof message === "function" ? message : null;
  elements.speakerResult.removeAttribute("data-i18n");
  elements.speakerResult.textContent = state.speakerResultFactory ? state.speakerResultFactory() : message;
}
function errorMessage(payload, fallback) { return payload && payload.error ? `${payload.error.message}. ${payload.error.retryable ? t("tryAgain") : t("checkInput")}` : fallback; }
function validateAudioSize(blob) { if (blob.size > MAX_AUDIO_BYTES) throw new Error(t("tooLarge")); }
function setCaptureDisabled(disabled) {
  elements.record.disabled = disabled;
  elements.upload.disabled = disabled;
  elements.uploadLabel.setAttribute("aria-disabled", String(disabled));
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(errorMessage(payload, `${t("requestFailed")} (${response.status})`));
  return payload;
}

function setConnection(kind, key) { state.connectionKind = kind; state.connectionKey = key; elements.status.className = `status-pill ${kind}`; elements.statusLabel.textContent = t(key); }
function setTurnState(key, detail = "") { state.turnKey = key; state.turnDetail = detail; elements.turnState.textContent = `${t(key)}${detail ? ` ${detail}` : ""}`; }
function resetPipeline() {
  elements.pipeline.querySelectorAll("li").forEach((item) => { item.removeAttribute("data-state"); item.removeAttribute("data-elapsed"); item.querySelector("output").textContent = t("waiting"); });
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
      item.dataset.elapsed = event.elapsed_ms === null ? "" : `${event.elapsed_ms.toFixed(1)} ms`;
      item.querySelector("output").textContent = item.dataset.elapsed || t(status);
    }
  }
  if (event.type === "pipeline.started") setTurnState("processing");
  if (event.type === "pipeline.completed") setTurnState("turnComplete");
  if (event.type === "pipeline.failed") setTurnState("failedAt", event.stage || "pipeline");
}

function connectEvents() {
  if (state.reconnectTimer) window.clearTimeout(state.reconnectTimer);
  if (state.socket) state.socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${scheme}://${location.host}/api/v1/sessions/${state.sessionId}/events`);
  state.socket.addEventListener("open", () => { state.reconnectAttempts = 0; setConnection("ready", "ready"); });
  state.socket.addEventListener("message", (message) => applyEvent(JSON.parse(message.data)));
  state.socket.addEventListener("close", () => {
    if (!state.sessionId) return;
    setConnection("", "reconnecting");
    const delay = Math.min(10000, 500 * (2 ** state.reconnectAttempts));
    state.reconnectAttempts += 1;
    state.reconnectTimer = setTimeout(connectEvents, delay);
  });
  state.socket.addEventListener("error", () => setConnection("error", "streamUnavailable"));
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
  state.lastWav = wav; updateSpeakerActions(); resetPipeline(); showError(""); setTurnState("uploadBounded");
  state.processing = true; setCaptureDisabled(true);
  try {
    const result = await request(`/api/v1/sessions/${state.sessionId}/turns`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: wav });
    elements.transcript.removeAttribute("data-i18n");
    elements.response.removeAttribute("data-i18n");
    elements.transcript.textContent = result.corrected_text || result.transcript;
    elements.transcript.className = "";
    elements.response.textContent = result.response;
    elements.response.className = "";
    elements.player.src = result.audio_url; elements.player.hidden = false;
    const total = Object.values(result.latencies_ms).reduce((sum, value) => sum + value, 0);
    elements.latency.textContent = `${total.toFixed(1)} ms`;
    setTurnState("turnComplete");
  } catch (error) { showError(() => `${error.message} ${t("recordClear")}`); setTurnState("turnAttention"); }
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
      state.recording = false; elements.record.classList.remove("recording"); elements.recordLabel.textContent = t("startRecording");
      state.stream.getTracks().forEach((track) => track.stop());
      setCaptureDisabled(true);
      try {
        const wav = await convertToWav(new Blob(state.chunks, { type: state.recorder.mimeType }));
        validateAudioSize(wav);
        await submitTurn(wav);
      }
      catch (error) { showError(() => `${error.message} ${t("tryWav")}`); setCaptureDisabled(false); }
    });
    state.recorder.start(); state.recording = true; elements.upload.disabled = true; elements.record.classList.add("recording"); elements.recordLabel.textContent = t("stopProcess"); setTurnState("recording");
    state.recordingTimer = setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000);
  } catch (error) { showError(() => `${t("micFailed")}: ${error.message}. ${t("allowMic")}`); }
}

function renderCapabilities(payload) {
  state.capabilitiesPayload = payload;
  clearChildren(elements.capabilities); elements.capabilities.setAttribute("aria-busy", "false");
  const limitationKeys = {
    "Signal-derived fixture text; not speech recognition.": "limitationAsr",
    "Whitespace and sentence casing only.": "limitationCorrection",
    "Punctuation and text-length heuristic only.": "limitationEndpoint",
    "Template response; no language model inference.": "limitationAgent",
    "Synthetic tone WAV; not natural speech.": "limitationTts",
    "Injected provider; consult deployment configuration for model limitations.": "limitationInjected",
    "Faster-Whisper local transcription; CPU inference.": "limitationWhisper",
    "Piper local Mandarin speech synthesis.": "limitationPiper"
  };
  payload.providers.forEach((provider) => {
    const item = element("li"); const name = element("strong", provider.stage); const badge = element("span", provider.development ? t("development") : t("functional"), "provider-badge");
    const translatedLimitations = provider.limitations.map((text) => limitationKeys[text] ? t(limitationKeys[text]) : text);
    const detail = element("span", provider.name); const limitation = element("small", translatedLimitations.join(" ") || t("defaultLimitation"));
    item.append(name, badge, detail, limitation); elements.capabilities.append(item);
  });
}

function renderSpeakers(payload) {
  state.speakersPayload = payload;
  clearChildren(elements.speakers);
  if (!payload.speakers.length) elements.speakers.append(element("li", t("noProfilesLong"), "empty-copy"));
  payload.speakers.forEach((speaker) => {
    const item = element("li"); const button = element("button"); button.type = "button"; button.setAttribute("aria-pressed", String(state.selectedSpeaker === speaker.id));
    button.append(element("strong", speaker.name), element("small", `${speaker.sample_count} ${t("sample")}`));
    button.addEventListener("click", () => { state.selectedSpeaker = speaker.id; renderSpeakers(payload); updateSpeakerActions(); setSpeakerResult(() => `${speaker.name} ${t("selected")}`); });
    item.append(button); elements.speakers.append(item);
  });
}

async function refreshSpeakers() { renderSpeakers(await request("/api/v1/speakers")); }

async function initialize() {
  try {
    const [health, capabilities, session] = await Promise.all([request("/api/v1/health"), request("/api/v1/capabilities"), request("/api/v1/sessions", { method: "POST" })]);
    if (health.status !== "ok") throw new Error(t("serviceUnhealthy"));
    state.sessionId = session.id; renderCapabilities(capabilities); await refreshSpeakers(); connectEvents(); setCaptureDisabled(false);
  } catch (error) { setConnection("error", "serviceUnavailable"); showError(() => `${error.message}. ${t("startService")}`); }
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
  } catch (error) { showError(() => `${error.message} ${t("readableAudio")}`); setCaptureDisabled(false); }
  finally { elements.upload.value = ""; }
});
elements.speakerForm.addEventListener("submit", async (event) => { event.preventDefault(); try { await request("/api/v1/speakers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: elements.speakerName.value }) }); elements.speakerName.value = ""; await refreshSpeakers(); setSpeakerResult(() => t("profileCreated")); } catch (error) { setSpeakerResult(error.message); } });
elements.enroll.addEventListener("click", async () => { try { const result = await request(`/api/v1/speakers/${state.selectedSpeaker}/samples`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: state.lastWav }); await refreshSpeakers(); setSpeakerResult(() => `${result.speaker.name} ${t("enrolled")}`); } catch (error) { setSpeakerResult(error.message); } });
elements.match.addEventListener("click", async () => { try { const result = await request("/api/v1/speakers/match", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: state.lastWav }); setSpeakerResult(() => result.match ? `${t("closest")}: ${result.match.name} (${(result.score * 100).toFixed(1)}%).` : t("noMatch")); } catch (error) { setSpeakerResult(error.message); } });
elements.rename.addEventListener("click", async () => { const name = window.prompt(t("promptRename")); if (!name) return; try { await request(`/api/v1/speakers/${state.selectedSpeaker}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, notes: "" }) }); await refreshSpeakers(); setSpeakerResult(() => t("renamed")); } catch (error) { setSpeakerResult(error.message); } });
elements.remove.addEventListener("click", async () => { if (!state.selectedSpeaker || !window.confirm(t("confirmDelete"))) return; try { await request(`/api/v1/speakers/${state.selectedSpeaker}`, { method: "DELETE" }); state.selectedSpeaker = null; await refreshSpeakers(); updateSpeakerActions(); setSpeakerResult(() => t("deleted")); } catch (error) { setSpeakerResult(error.message); } });

elements.language.addEventListener("click", () => setLocale(currentLocale === "zh-TW" ? "en" : "zh-TW"));
setLocale(readStoredLocale() === "en" ? "en" : DEFAULT_LOCALE, false);

initialize();

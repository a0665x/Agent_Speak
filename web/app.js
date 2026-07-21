"use strict";

const localeApi = window.AgentSpeakLocale;
let storedLocale = null;
try {
  storedLocale = localStorage.getItem(localeApi.STORAGE_KEY);
} catch (_) {
  storedLocale = null;
}
let activeLocale = localeApi.resolveLocale(window.location.search, storedLocale);
let statusState = "loading";
localeApi.applyLocale(document, activeLocale);

const elements = {
  summary: document.querySelector("#status-summary"),
  gateway: document.querySelector("#status-gateway"),
  asr: document.querySelector("#status-asr"),
  correction: document.querySelector("#status-correction"),
  card: document.querySelector("#system-status"),
};

function providerLabel(provider) {
  if (!provider) return localeApi.translate(activeLocale, "status.providerUnavailable").toUpperCase();
  const device = String(provider.device || "unknown").toUpperCase();
  const key = provider.ready ? "status.providerReady" : "status.providerDown";
  return `${localeApi.translate(activeLocale, key).toUpperCase()} · ${device}`;
}

function renderStatusSummary() {
  elements.summary.textContent = localeApi.translate(activeLocale, `status.${statusState}`);
}

async function loadSystemStatus() {
  try {
    const [healthResponse, capabilitiesResponse] = await Promise.all([
      fetch("/api/v1/health"),
      fetch("/api/v1/capabilities"),
    ]);
    if (!healthResponse.ok || !capabilitiesResponse.ok) throw new Error("status unavailable");
    const health = await healthResponse.json();
    const capabilities = await capabilitiesResponse.json();
    const providers = Array.isArray(capabilities.providers) ? capabilities.providers : [];
    const asr = providers.find((provider) => provider.stage === "asr");
    const correction = providers.find((provider) => provider.stage === "correction");
    elements.gateway.textContent = `${localeApi.translate(activeLocale, "status.providerReady").toUpperCase()} · v${health.version}`;
    elements.asr.textContent = providerLabel(asr);
    elements.correction.textContent = providerLabel(correction);
    statusState = "ready";
    renderStatusSummary();
    elements.card.dataset.state = "ready";
  } catch (_) {
    elements.gateway.textContent = localeApi.translate(activeLocale, "status.providerUnavailable").toUpperCase();
    elements.asr.textContent = "—";
    elements.correction.textContent = "—";
    statusState = "unavailable";
    renderStatusSummary();
    elements.card.dataset.state = "error";
  }
}

document.querySelector("#language-select")?.addEventListener("change", (event) => {
  activeLocale = event.currentTarget.value;
  try {
    localStorage.setItem(localeApi.STORAGE_KEY, activeLocale);
  } catch (_) {
    // The URL still carries the selected language when storage is unavailable.
  }
  localeApi.applyLocale(document, activeLocale);
  renderStatusSummary();
  const nextUrl = localeApi.withLocale(window.location.pathname + window.location.search, activeLocale);
  window.history.replaceState(null, "", nextUrl);
});

void loadSystemStatus();

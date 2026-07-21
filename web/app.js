"use strict";

const elements = {
  summary: document.querySelector("#status-summary"),
  gateway: document.querySelector("#status-gateway"),
  asr: document.querySelector("#status-asr"),
  correction: document.querySelector("#status-correction"),
  card: document.querySelector("#system-status"),
};

function providerLabel(provider) {
  if (!provider) return "UNAVAILABLE";
  const device = String(provider.device || "unknown").toUpperCase();
  return `${provider.ready ? "READY" : "DOWN"} · ${device}`;
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
    elements.gateway.textContent = `READY · v${health.version}`;
    elements.asr.textContent = providerLabel(asr);
    elements.correction.textContent = providerLabel(correction);
    elements.summary.textContent = "Gateway 與模型能力已連線";
    elements.card.dataset.state = "ready";
  } catch (_) {
    elements.gateway.textContent = "UNAVAILABLE";
    elements.asr.textContent = "—";
    elements.correction.textContent = "—";
    elements.summary.textContent = "目前無法讀取本機服務狀態";
    elements.card.dataset.state = "error";
  }
}

void loadSystemStatus();

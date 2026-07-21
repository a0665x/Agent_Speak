"use strict";

const languageSelect = document.querySelector("#language-select");
const currentLocale = languageSelect?.dataset.currentLocale || "en";

try {
  localStorage.setItem("agent-speak-locale", currentLocale);
} catch (_) {
  // The query parameter remains the source of truth when storage is unavailable.
}

languageSelect?.addEventListener("change", (event) => {
  const locale = event.currentTarget.value;
  try {
    localStorage.setItem("agent-speak-locale", locale);
  } catch (_) {
    // Navigation still preserves the selected locale.
  }
  window.location.assign(`/docs?lang=${encodeURIComponent(locale)}`);
});

"use strict";

(function exposeLocale(globalScope) {
  const SUPPORTED_LOCALES = ["en", "zh-TW", "ja", "ko"];
  const DEFAULT_LOCALE = "en";
  const STORAGE_KEY = "agent-speak-locale";

  const messages = {
    en: {
      "meta.description": "Agent Speak local speech gateway: APIs, realtime ASR, and live system status.",
      "page.title": "Agent Speak · Local Speech Gateway",
      "skip": "Skip to main content",
      "nav.aria": "Site navigation",
      "brand.aria": "Agent Speak home",
      "language.label": "Language",
      "hero.eyebrow": "LOCAL · PRIVATE · REALTIME",
      "hero.title": "Turn voice into",
      "hero.titleAccent": "a usable signal.",
      "hero.lede": "A local speech gateway that stays independent of any one Agent. Start with the API, or watch speech become text in realtime.",
      "hero.action": "Open ASR Realtime",
      "hero.imageAlt": "Abstract illustration of sound waves passing through a local processing core and becoming text",
      "hero.caption": "Audio → intelligence-ready text",
      "card.api.description": "Explore the `/api/v1` Swagger contract",
      "card.realtime.description": "Continuous VAD and realtime correction",
      "status.title": "System Status",
      "status.loading": "Checking the local service…",
      "status.ready": "Gateway and model capabilities are connected",
      "status.unavailable": "Local service status is currently unavailable",
      "status.providerUnavailable": "UNAVAILABLE",
      "status.providerReady": "READY",
      "status.providerDown": "DOWN",
      "pipeline.eyebrow": "THE LOCAL PATH",
      "pipeline.title": "Make every step of speech visible.",
      "pipeline.vad": "Voice detected",
      "pipeline.endpoint": "Pause understood",
      "pipeline.asr": "Speech to text",
      "pipeline.correction": "Context refined",
      "footer.safety": "Local-first · No automatic microphone access",
    },
    "zh-TW": {
      "meta.description": "Agent Speak 本機語音閘道：API、即時 ASR 與系統狀態。",
      "page.title": "Agent Speak · 本機語音閘道",
      "skip": "跳至主要內容",
      "nav.aria": "網站導覽",
      "brand.aria": "Agent Speak 首頁",
      "language.label": "語言",
      "hero.eyebrow": "本機 · 私密 · 即時",
      "hero.title": "讓聲音，",
      "hero.titleAccent": "成為可用的訊號。",
      "hero.lede": "一個不綁定單一 Agent 的本機語音閘道。從 API 開始，或直接看即時語音如何成為文字。",
      "hero.action": "開啟 ASR Realtime",
      "hero.imageAlt": "聲波通過本機處理核心轉換成文字的抽象示意圖",
      "hero.caption": "音訊 → 可供智慧處理的文字",
      "card.api.description": "查看 `/api/v1` Swagger 契約",
      "card.realtime.description": "Continuous VAD 與即時校正",
      "status.title": "系統狀態",
      "status.loading": "正在確認本機服務…",
      "status.ready": "Gateway 與模型能力已連線",
      "status.unavailable": "目前無法讀取本機服務狀態",
      "status.providerUnavailable": "無法使用",
      "status.providerReady": "就緒",
      "status.providerDown": "離線",
      "pipeline.eyebrow": "本機處理路徑",
      "pipeline.title": "聲音走過的每一步，都看得見。",
      "pipeline.vad": "偵測到人聲",
      "pipeline.endpoint": "理解停頓",
      "pipeline.asr": "語音轉文字",
      "pipeline.correction": "依上下文校正",
      "footer.safety": "本機優先 · 不會自動存取麥克風",
    },
    ja: {
      "meta.description": "Agent Speak ローカル音声 gateway：API、realtime ASR、システム状態。",
      "page.title": "Agent Speak · ローカル音声 Gateway",
      "skip": "メインコンテンツへ移動",
      "nav.aria": "サイトナビゲーション",
      "brand.aria": "Agent Speak ホーム",
      "language.label": "言語",
      "hero.eyebrow": "ローカル · プライベート · リアルタイム",
      "hero.title": "声を、",
      "hero.titleAccent": "使える signal へ。",
      "hero.lede": "特定の Agent に依存しないローカル音声 gateway。API から始めるか、音声が realtime にテキストになる様子を確認できます。",
      "hero.action": "ASR Realtime を開く",
      "hero.imageAlt": "音波がローカル処理 core を通ってテキストへ変換される抽象イメージ",
      "hero.caption": "音声 → intelligence-ready text",
      "card.api.description": "`/api/v1` Swagger contract を確認",
      "card.realtime.description": "継続 VAD と realtime 補正",
      "status.title": "システム状態",
      "status.loading": "ローカル service を確認しています…",
      "status.ready": "Gateway とモデル機能に接続しました",
      "status.unavailable": "ローカル service の状態を取得できません",
      "status.providerUnavailable": "利用不可",
      "status.providerReady": "準備完了",
      "status.providerDown": "停止",
      "pipeline.eyebrow": "ローカル処理経路",
      "pipeline.title": "音声処理のすべての段階を可視化。",
      "pipeline.vad": "発話を検出",
      "pipeline.endpoint": "間を理解",
      "pipeline.asr": "音声をテキスト化",
      "pipeline.correction": "文脈を補正",
      "footer.safety": "ローカル優先 · マイクへ自動アクセスしません",
    },
    ko: {
      "meta.description": "Agent Speak 로컬 음성 gateway: API, realtime ASR 및 시스템 상태.",
      "page.title": "Agent Speak · 로컬 음성 Gateway",
      "skip": "주요 콘텐츠로 이동",
      "nav.aria": "사이트 탐색",
      "brand.aria": "Agent Speak 홈",
      "language.label": "언어",
      "hero.eyebrow": "로컬 · 프라이빗 · 실시간",
      "hero.title": "목소리를",
      "hero.titleAccent": "쓸 수 있는 signal로.",
      "hero.lede": "특정 Agent에 종속되지 않는 로컬 음성 gateway입니다. API로 시작하거나 음성이 realtime 텍스트가 되는 과정을 확인하세요.",
      "hero.action": "ASR Realtime 열기",
      "hero.imageAlt": "음파가 로컬 처리 core를 통과해 텍스트로 변환되는 추상 이미지",
      "hero.caption": "오디오 → intelligence-ready text",
      "card.api.description": "`/api/v1` Swagger contract 살펴보기",
      "card.realtime.description": "연속 VAD 및 realtime 교정",
      "status.title": "시스템 상태",
      "status.loading": "로컬 서비스를 확인하는 중…",
      "status.ready": "Gateway와 모델 기능이 연결되었습니다",
      "status.unavailable": "현재 로컬 서비스 상태를 가져올 수 없습니다",
      "status.providerUnavailable": "사용 불가",
      "status.providerReady": "준비됨",
      "status.providerDown": "중단됨",
      "pipeline.eyebrow": "로컬 처리 경로",
      "pipeline.title": "음성 처리의 모든 단계를 한눈에.",
      "pipeline.vad": "음성 감지",
      "pipeline.endpoint": "멈춤 이해",
      "pipeline.asr": "음성을 텍스트로",
      "pipeline.correction": "문맥 교정",
      "footer.safety": "로컬 우선 · 마이크에 자동 접근하지 않음",
    },
  };

  function resolveLocale(search, storedLocale) {
    const params = new URLSearchParams(search || "");
    if (params.has("lang")) {
      const requested = params.get("lang");
      return SUPPORTED_LOCALES.includes(requested) ? requested : DEFAULT_LOCALE;
    }
    return SUPPORTED_LOCALES.includes(storedLocale) ? storedLocale : DEFAULT_LOCALE;
  }

  function translate(locale, key) {
    const language = SUPPORTED_LOCALES.includes(locale) ? locale : DEFAULT_LOCALE;
    return messages[language][key] || messages.en[key] || key;
  }

  function withLocale(path, locale) {
    const [pathname, query = ""] = path.split("?", 2);
    const params = new URLSearchParams(query);
    params.set("lang", SUPPORTED_LOCALES.includes(locale) ? locale : DEFAULT_LOCALE);
    return `${pathname}?${params.toString()}`;
  }

  function applyLocale(documentRef, locale) {
    documentRef.documentElement.lang = locale;
    documentRef.title = translate(locale, "page.title");
    const meta = documentRef.querySelector('meta[name="description"]');
    if (meta) meta.content = translate(locale, "meta.description");
    documentRef.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = translate(locale, element.dataset.i18n);
    });
    documentRef.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", translate(locale, element.dataset.i18nAriaLabel));
    });
    documentRef.querySelectorAll("[data-i18n-alt]").forEach((element) => {
      element.setAttribute("alt", translate(locale, element.dataset.i18nAlt));
    });
    documentRef.querySelectorAll("[data-route]").forEach((element) => {
      element.setAttribute("href", withLocale(element.dataset.route, locale));
    });
    const select = documentRef.querySelector("#language-select");
    if (select) {
      select.value = locale;
      select.setAttribute("aria-label", translate(locale, "language.label"));
    }
  }

  const api = {
    DEFAULT_LOCALE,
    STORAGE_KEY,
    SUPPORTED_LOCALES,
    messages,
    resolveLocale,
    translate,
    withLocale,
    applyLocale,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (globalScope) globalScope.AgentSpeakLocale = api;
})(typeof window !== "undefined" ? window : globalThis);

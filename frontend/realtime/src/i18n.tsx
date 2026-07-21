import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export const SUPPORTED_LOCALES = ['en', 'zh-TW', 'ja', 'ko'] as const;
export type Locale = typeof SUPPORTED_LOCALES[number];
const DEFAULT_LOCALE: Locale = 'en';
const STORAGE_KEY = 'agent-speak-locale';

const en = {
  'skip': 'Skip to main content',
  'language.label': 'Language',
  'nav.projectHome': 'Project Home',
  'nav.aria': 'Realtime navigation',
  'hero.eyebrow': 'CONTINUOUS SPEECH EXPERIENCE',
  'hero.title': 'Speak. See it flow.',
  'hero.titleLead': 'Speak.',
  'hero.titleAccent': 'See it flow.',
  'hero.lede': 'Voice comes in and text takes shape. Every utterance, pause, and correction appears through real pipeline events.',
  'session.label': 'SESSION',
  'session.notStarted': 'not started',
  'session.aria': 'Current session: {value}',
  'error.retry': 'Check the worker status and headset connection, then try again.',
  'error.deviceCheck': 'Unable to check headset devices',
  'error.createSession': 'Unable to create a realtime session',
  'error.start': 'Unable to start realtime listening',
  'warning.pipeline': 'Pipeline warning: {value}',
  'controls.aria': 'Realtime speech controls',
  'controls.checking': 'Checking…',
  'controls.checkDevices': 'Check devices',
  'controls.start': 'Start Listening',
  'controls.stop': 'Stop Listening',
  'controls.startAria': 'Start realtime listening',
  'controls.stopAria': 'Stop realtime listening',
  'device.eyebrow': 'DEVICE GATE',
  'device.inputMissing': 'Microphone not confirmed',
  'device.outputMissing': 'Audio output not confirmed',
  'speech.label': 'Speech language',
  'speech.auto': 'Auto detect',
  'speech.locked': 'Locked for this session: {value}',
  'speech.nextSession': 'Applies to the next session',
  'process.eyebrow': 'CONTINUOUS CYCLE',
  'process.title': 'Realtime processing',
  'stage.listening': 'Listening',
  'stage.listeningDetail': 'Awaiting voice',
  'stage.voice': 'Voice detected',
  'stage.voiceDetail': 'VAD active',
  'stage.asr': 'ASR partial',
  'stage.asrDetail': 'Rolling text',
  'stage.endpoint': 'Endpoint',
  'stage.endpointDetail': 'Pause / resume',
  'stage.correction': 'Correction',
  'stage.correctionDetail': 'Final text',
  'stage.unknown': 'STANDBY',
  'audio.waveform': 'Live microphone waveform, current state: {value}',
  'audio.ready': 'Waiting for device',
  'audio.listening': 'Listening',
  'audio.speech': 'Voice detected',
  'audio.endpoint': 'Detecting endpoint',
  'audio.finalizing': 'Finalizing transcript',
  'audio.correcting': 'Correcting text',
  'audio.stopped': 'Stopped',
  'pipeline.aria': 'Realtime pipeline status',
  'pipeline.standby': 'standby',
  'pipeline.pending': '{value} pending',
  'pipeline.processing': 'processing',
  'models.eyebrow': 'ACTIVE MODELS',
  'models.aria': 'Inference worker devices',
  'models.streaming': 'STREAMING',
  'models.standby': 'STANDBY',
  'models.correction': 'Correction',
  'models.endpoint': 'Endpoint',
  'models.hard': 'hard {value} ms',
  'models.queue': 'ASR Queue',
  'models.pending': '{value} pending',
  'transcript.eyebrow': 'LIVE TRANSCRIPT',
  'transcript.title': 'Utterance transcript',
  'transcript.empty': 'Recognized utterances will appear here after listening begins.',
  'transcript.locked': 'Locked',
  'transcript.partial': 'Partial transcript',
  'transcript.editable': 'May be corrected with the next utterance',
  'transcript.rowAria': '{text}, {status}',
  'graph.eyebrow': 'UTTERANCE GRAPH',
  'graph.title': 'ASR text relationships',
  'graph.description': 'Each endpoint is one text block; solid lines show time and dashed lines show local text similarity.',
  'graph.legend': 'Graph legend',
  'graph.timeline': 'Time order',
  'graph.similarity': 'Text similarity',
  'graph.empty': 'Nodes appear here after the first corrected utterance is complete.',
  'graph.canvas': 'Text relationship graph for completed speech segments',
  'graph.node': 'Speech segment {value}',
  'sr.devicesReady': 'Zone Vibe 100 input and output confirmed',
  'sr.devicesNotReady': 'Zone Vibe 100 input and output not checked',
} as const;

export type MessageKey = keyof typeof en;
type Catalog = Record<MessageKey, string>;

const zhTW: Catalog = {
  'skip': '跳至主要內容',
  'language.label': '語言', 'nav.projectHome': '專案首頁', 'nav.aria': '即時語音導覽',
  'hero.eyebrow': '持續語音體驗', 'hero.title': '說話，看見文字流動。', 'hero.titleLead': '說話。', 'hero.titleAccent': '看見文字流動。',
  'hero.lede': '聲音進來，文字成形。每次說話、停頓與校正，都由真實 pipeline event 即時呈現。',
  'session.label': '工作階段', 'session.notStarted': '尚未開始', 'session.aria': '目前工作階段：{value}',
  'error.retry': '請確認 worker 狀態與耳機連線後重試。', 'error.deviceCheck': '無法檢查耳機裝置',
  'error.createSession': '無法建立 realtime 工作階段', 'error.start': '無法開始即時聆聽', 'warning.pipeline': 'Pipeline 警告：{value}',
  'controls.aria': '即時語音控制', 'controls.checking': '正在檢查…', 'controls.checkDevices': '檢查裝置',
  'controls.start': '開始聆聽', 'controls.stop': '停止聆聽', 'controls.startAria': '開始即時聆聽', 'controls.stopAria': '停止即時聆聽',
  'device.eyebrow': '裝置閘門', 'device.inputMissing': '麥克風尚未確認', 'device.outputMissing': '音訊輸出尚未確認',
  'speech.label': '語音語言', 'speech.auto': '自動偵測', 'speech.locked': '本工作階段已鎖定：{value}', 'speech.nextSession': '將套用至下一個工作階段',
  'process.eyebrow': '持續循環', 'process.title': '即時處理', 'stage.listening': '聆聽中', 'stage.listeningDetail': '等待語音',
  'stage.voice': '偵測到語音', 'stage.voiceDetail': 'VAD 啟用', 'stage.asr': 'ASR 暫定結果', 'stage.asrDetail': '文字持續更新',
  'stage.endpoint': '語句端點', 'stage.endpointDetail': '停頓／繼續', 'stage.correction': '文字校正', 'stage.correctionDetail': '最終文字', 'stage.unknown': '待命',
  'audio.waveform': '即時麥克風波形，目前狀態：{value}', 'audio.ready': '等待裝置', 'audio.listening': '正在聆聽',
  'audio.speech': '偵測到語音', 'audio.endpoint': '判斷句尾', 'audio.finalizing': '最終辨識', 'audio.correcting': '校正文字', 'audio.stopped': '已停止',
  'pipeline.aria': '即時 pipeline 狀態', 'pipeline.standby': '待命', 'pipeline.pending': '{value} 筆等待中', 'pipeline.processing': '處理中',
  'models.eyebrow': '啟用中的模型', 'models.aria': '推論 worker 裝置', 'models.streaming': '串流中', 'models.standby': '待命',
  'models.correction': '文字校正', 'models.endpoint': '語句端點', 'models.hard': '最長 {value} ms', 'models.queue': 'ASR 佇列', 'models.pending': '{value} 筆等待中',
  'transcript.eyebrow': '即時逐字稿', 'transcript.title': '逐句辨識文字', 'transcript.empty': '開始聆聽後，辨識文字會依序出現在這裡。',
  'transcript.locked': '已鎖定', 'transcript.partial': '暫定辨識', 'transcript.editable': '仍可隨下一句校正', 'transcript.rowAria': '{text}，{status}',
  'graph.eyebrow': '語句關係圖', 'graph.title': 'ASR 文字關係', 'graph.description': '每個 endpoint 是一段文字；實線代表時間，虛線代表本機文字相似度。',
  'graph.legend': '圖例', 'graph.timeline': '時間順序', 'graph.similarity': '文字相似', 'graph.empty': '完成第一段校正後，節點會出現在這裡。',
  'graph.canvas': '已完成語音片段的文字關係圖', 'graph.node': '語音片段 {value}',
  'sr.devicesReady': 'Zone Vibe 100 輸入與輸出已確認', 'sr.devicesNotReady': '尚未檢查 Zone Vibe 100 輸入與輸出',
};

const ja: Catalog = {
  'skip': 'メインコンテンツへ移動',
  'language.label': '言語', 'nav.projectHome': 'プロジェクトホーム', 'nav.aria': 'Realtime ナビゲーション',
  'hero.eyebrow': '継続音声エクスペリエンス', 'hero.title': '話す。流れが見える。', 'hero.titleLead': '話す。', 'hero.titleAccent': '流れが見える。',
  'hero.lede': '音声が入り、テキストが形になります。発話、間、補正のすべてを実際の pipeline event で realtime に表示します。',
  'session.label': 'セッション', 'session.notStarted': '未開始', 'session.aria': '現在の session：{value}',
  'error.retry': 'worker の状態と headset 接続を確認して、もう一度お試しください。', 'error.deviceCheck': 'headset device を確認できません',
  'error.createSession': 'realtime session を作成できません', 'error.start': 'realtime listening を開始できません', 'warning.pipeline': 'Pipeline warning：{value}',
  'controls.aria': 'Realtime 音声コントロール', 'controls.checking': '確認中…', 'controls.checkDevices': 'Device を確認',
  'controls.start': 'Listening を開始', 'controls.stop': 'Listening を停止', 'controls.startAria': 'Realtime listening を開始', 'controls.stopAria': 'Realtime listening を停止',
  'device.eyebrow': 'DEVICE GATE', 'device.inputMissing': 'マイク未確認', 'device.outputMissing': '音声出力未確認',
  'speech.label': '音声言語', 'speech.auto': '自動検出', 'speech.locked': 'この session で固定：{value}', 'speech.nextSession': '次の session に適用されます',
  'process.eyebrow': '継続サイクル', 'process.title': 'Realtime 処理', 'stage.listening': 'Listening', 'stage.listeningDetail': '音声を待機',
  'stage.voice': '音声を検出', 'stage.voiceDetail': 'VAD 動作中', 'stage.asr': 'ASR 暫定結果', 'stage.asrDetail': 'テキスト更新中',
  'stage.endpoint': 'Endpoint', 'stage.endpointDetail': '間／再開', 'stage.correction': '補正', 'stage.correctionDetail': '最終テキスト', 'stage.unknown': '待機',
  'audio.waveform': 'Realtime マイク波形。現在の状態：{value}', 'audio.ready': 'device を待機', 'audio.listening': 'Listening 中',
  'audio.speech': '音声を検出', 'audio.endpoint': 'endpoint を判定', 'audio.finalizing': '文字起こしを確定', 'audio.correcting': 'テキストを補正', 'audio.stopped': '停止',
  'pipeline.aria': 'Realtime pipeline 状態', 'pipeline.standby': '待機', 'pipeline.pending': '{value} 件待機', 'pipeline.processing': '処理中',
  'models.eyebrow': '有効なモデル', 'models.aria': '推論 worker device', 'models.streaming': 'STREAMING', 'models.standby': '待機',
  'models.correction': '補正', 'models.endpoint': 'Endpoint', 'models.hard': '最大 {value} ms', 'models.queue': 'ASR Queue', 'models.pending': '{value} 件待機',
  'transcript.eyebrow': 'LIVE TRANSCRIPT', 'transcript.title': '発話テキスト', 'transcript.empty': 'Listening を開始すると、認識した発話がここに表示されます。',
  'transcript.locked': '確定', 'transcript.partial': '暫定認識', 'transcript.editable': '次の発話で補正される場合があります', 'transcript.rowAria': '{text}、{status}',
  'graph.eyebrow': '発話グラフ', 'graph.title': 'ASR テキストの関係', 'graph.description': '各 endpoint は 1 つのテキスト block です。実線は時間、破線はローカル text similarity を示します。',
  'graph.legend': 'グラフ凡例', 'graph.timeline': '時間順', 'graph.similarity': 'テキスト類似度', 'graph.empty': '最初の補正済み発話が完了すると node が表示されます。',
  'graph.canvas': '完了した音声 segment のテキスト関係グラフ', 'graph.node': '音声 segment {value}',
  'sr.devicesReady': 'Zone Vibe 100 の入力と出力を確認済み', 'sr.devicesNotReady': 'Zone Vibe 100 の入力と出力は未確認',
};

const ko: Catalog = {
  'skip': '주요 콘텐츠로 이동',
  'language.label': '언어', 'nav.projectHome': '프로젝트 홈', 'nav.aria': 'Realtime 탐색',
  'hero.eyebrow': '연속 음성 경험', 'hero.title': '말하고, 흐름을 확인하세요.', 'hero.titleLead': '말하세요.', 'hero.titleAccent': '흐름을 확인하세요.',
  'hero.lede': '음성이 들어오면 텍스트가 만들어집니다. 발화, 멈춤, 교정을 실제 pipeline event로 realtime 표시합니다.',
  'session.label': '세션', 'session.notStarted': '시작 전', 'session.aria': '현재 session: {value}',
  'error.retry': 'worker 상태와 headset 연결을 확인한 뒤 다시 시도하세요.', 'error.deviceCheck': 'headset device를 확인할 수 없습니다',
  'error.createSession': 'realtime session을 만들 수 없습니다', 'error.start': 'realtime listening을 시작할 수 없습니다', 'warning.pipeline': 'Pipeline 경고: {value}',
  'controls.aria': 'Realtime 음성 제어', 'controls.checking': '확인 중…', 'controls.checkDevices': 'Device 확인',
  'controls.start': 'Listening 시작', 'controls.stop': 'Listening 중지', 'controls.startAria': 'Realtime listening 시작', 'controls.stopAria': 'Realtime listening 중지',
  'device.eyebrow': 'DEVICE GATE', 'device.inputMissing': '마이크 확인 전', 'device.outputMissing': '오디오 출력 확인 전',
  'speech.label': '음성 언어', 'speech.auto': '자동 감지', 'speech.locked': '현재 session에 고정: {value}', 'speech.nextSession': '다음 session에 적용됩니다',
  'process.eyebrow': '연속 사이클', 'process.title': 'Realtime 처리', 'stage.listening': 'Listening', 'stage.listeningDetail': '음성 대기',
  'stage.voice': '음성 감지', 'stage.voiceDetail': 'VAD 활성', 'stage.asr': 'ASR 부분 결과', 'stage.asrDetail': '텍스트 업데이트',
  'stage.endpoint': 'Endpoint', 'stage.endpointDetail': '멈춤／재개', 'stage.correction': '교정', 'stage.correctionDetail': '최종 텍스트', 'stage.unknown': '대기',
  'audio.waveform': 'Realtime 마이크 파형, 현재 상태: {value}', 'audio.ready': 'device 대기', 'audio.listening': 'Listening 중',
  'audio.speech': '음성 감지', 'audio.endpoint': 'endpoint 판단', 'audio.finalizing': '전사 확정', 'audio.correcting': '텍스트 교정', 'audio.stopped': '중지됨',
  'pipeline.aria': 'Realtime pipeline 상태', 'pipeline.standby': '대기', 'pipeline.pending': '{value}개 대기', 'pipeline.processing': '처리 중',
  'models.eyebrow': '활성 모델', 'models.aria': '추론 worker device', 'models.streaming': 'STREAMING', 'models.standby': '대기',
  'models.correction': '교정', 'models.endpoint': 'Endpoint', 'models.hard': '최대 {value} ms', 'models.queue': 'ASR Queue', 'models.pending': '{value}개 대기',
  'transcript.eyebrow': 'LIVE TRANSCRIPT', 'transcript.title': '발화 텍스트', 'transcript.empty': 'Listening을 시작하면 인식된 발화가 여기에 표시됩니다.',
  'transcript.locked': '확정됨', 'transcript.partial': '부분 전사', 'transcript.editable': '다음 발화에 따라 교정될 수 있음', 'transcript.rowAria': '{text}, {status}',
  'graph.eyebrow': '발화 그래프', 'graph.title': 'ASR 텍스트 관계', 'graph.description': '각 endpoint는 하나의 텍스트 block입니다. 실선은 시간, 점선은 로컬 text similarity를 나타냅니다.',
  'graph.legend': '그래프 범례', 'graph.timeline': '시간 순서', 'graph.similarity': '텍스트 유사도', 'graph.empty': '첫 교정 발화가 완료되면 node가 여기에 표시됩니다.',
  'graph.canvas': '완료된 음성 segment의 텍스트 관계 그래프', 'graph.node': '음성 segment {value}',
  'sr.devicesReady': 'Zone Vibe 100 입력 및 출력 확인됨', 'sr.devicesNotReady': 'Zone Vibe 100 입력 및 출력 확인 전',
};

export const messages: Record<Locale, Catalog> = { en, 'zh-TW': zhTW, ja, ko };

export function resolveLocale(search: string, storedLocale: string | null): Locale {
  const params = new URLSearchParams(search);
  if (params.has('lang')) {
    const requested = params.get('lang');
    return SUPPORTED_LOCALES.includes(requested as Locale) ? requested as Locale : DEFAULT_LOCALE;
  }
  return SUPPORTED_LOCALES.includes(storedLocale as Locale) ? storedLocale as Locale : DEFAULT_LOCALE;
}

export function localizedHref(path: string, locale: Locale): string {
  const [pathname, query = ''] = path.split('?', 2);
  const params = new URLSearchParams(query);
  params.set('lang', locale);
  return `${pathname}?${params.toString()}`;
}

function format(template: string, values?: Record<string, string | number>): string {
  return Object.entries(values ?? {}).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)), template
  );
}

type I18nValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, values?: Record<string, string | number>) => string;
  href: (path: string) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

function readStoredLocale(): string | null {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

export function I18nProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale ?? resolveLocale(window.location.search, readStoredLocale()));

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((nextLocale: Locale) => {
    setLocaleState(nextLocale);
    document.documentElement.lang = nextLocale;
    try { localStorage.setItem(STORAGE_KEY, nextLocale); } catch { /* URL remains the fallback. */ }
    const nextUrl = localizedHref(window.location.pathname + window.location.search, nextLocale);
    window.history.replaceState(null, '', nextUrl);
  }, []);

  const value = useMemo<I18nValue>(() => ({
    locale,
    setLocale,
    t: (key, values) => format(messages[locale][key] ?? messages.en[key], values),
    href: path => localizedHref(path, locale),
  }), [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
}

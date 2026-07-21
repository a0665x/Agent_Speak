import { Languages, LockKeyhole } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  SPEECH_LANGUAGES,
  speechLanguageName,
  type SpeechLanguage,
} from '../speechLanguage';

type Props = {
  value: SpeechLanguage;
  locked: SpeechLanguage | null;
  active: boolean;
  onChange: (value: SpeechLanguage) => void;
};

export function SpeechLanguageControl({ value, locked, active, onChange }: Props) {
  const { t } = useI18n();
  const lockedName = locked ? speechLanguageName(locked, t('speech.auto')) : '';
  const appliesNext = active && locked !== null && value !== locked;

  return (
    <section className="speech-language-control" aria-labelledby="speech-language-label">
      <label id="speech-language-label" htmlFor="speech-language-select">
        <Languages aria-hidden="true" />
        <span>{t('speech.label')}</span>
      </label>
      <select
        id="speech-language-select"
        aria-label={t('speech.label')}
        value={value}
        onChange={event => onChange(event.target.value as SpeechLanguage)}
      >
        {SPEECH_LANGUAGES.map(language => (
          <option key={language} value={language}>
            {speechLanguageName(language, t('speech.auto'))}
          </option>
        ))}
      </select>
      <div className="speech-language-meta" aria-live="polite">
        {locked && <span className="speech-language-locked"><LockKeyhole aria-hidden="true" />{t('speech.locked', { value: lockedName })}</span>}
        {appliesNext && <span className="speech-language-next">{t('speech.nextSession')}</span>}
      </div>
    </section>
  );
}

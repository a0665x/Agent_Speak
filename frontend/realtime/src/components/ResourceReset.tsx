import { RefreshCw } from 'lucide-react';
import { useRef, useState } from 'react';
import type { ResourcePhase } from '../resources';

type ResourceResetProps = {
  label: string;
  phase: ResourcePhase | null;
  busy: boolean;
  onReset: () => void | Promise<void>;
  confirmReset?: () => boolean | Promise<boolean>;
  phaseLabel: (phase: ResourcePhase) => string;
  error?: string;
  recoveryHint?: string | null;
  reducedMotion?: boolean;
};

export function ResourceReset({
  label,
  phase,
  busy,
  onReset,
  confirmReset,
  phaseLabel,
  error = '',
  recoveryHint = null,
  reducedMotion = false,
}: ResourceResetProps) {
  const pending = useRef(false);
  const [internalBusy, setInternalBusy] = useState(false);
  const [internalError, setInternalError] = useState('');
  const disabled = busy || internalBusy;

  const reset = async () => {
    if (disabled || pending.current) return;
    pending.current = true;
    setInternalError('');
    try {
      if (confirmReset && !await confirmReset()) return;
      setInternalBusy(true);
      await onReset();
    } catch (cause) {
      setInternalError(
        cause instanceof Error
          ? cause.message
          : 'Resource reset failed',
      );
    } finally {
      pending.current = false;
      setInternalBusy(false);
    }
  };

  const visibleError = error || internalError;
  return (
    <div
      className="resource-reset"
      data-testid="resource-reset"
      data-reduced-motion={reducedMotion ? 'true' : 'false'}
    >
      <button
        className="resource-reset__button"
        type="button"
        disabled={disabled}
        aria-busy={disabled}
        onClick={() => void reset()}
      >
        <RefreshCw
          aria-hidden="true"
          className={disabled ? 'resource-reset__spinner' : undefined}
          size={16}
          strokeWidth={1.8}
        />
        <span>{label}</span>
      </button>
      {phase && (
        <span
          className={`resource-reset__phase phase-${phase}`}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {phaseLabel(phase)}
        </span>
      )}
      {visibleError && (
        <span className="resource-reset__error" role="alert">
          <strong>{visibleError}</strong>
          {recoveryHint && <code>{recoveryHint}</code>}
        </span>
      )}
    </div>
  );
}

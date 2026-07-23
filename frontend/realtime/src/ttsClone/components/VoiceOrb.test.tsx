import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { VoiceOrb } from './VoiceOrb';

describe('Voice Orb', () => {
  it.each([
    ['idle', 'Ready'],
    ['recording', 'Recording'],
    ['validating', 'Checking reference'],
    ['queued', 'Queued'],
    ['generating', 'Generating'],
    ['audio-ready', 'Audio ready'],
    ['playing', 'Playing'],
    ['complete', 'Complete'],
    ['unavailable', 'Unavailable'],
    ['error', 'Needs attention'],
  ] as const)('exposes semantic %s state', (state, label) => {
    render(
      <VoiceOrb
        state={state}
        amplitude={state === 'recording' ? 0.8 : 0}
        voiced={state === 'recording'}
        reducedMotion={false}
        label={label}
      />,
    );

    expect(screen.getByTestId('voice-orb')).toHaveAttribute('data-state', state);
    expect(screen.getByRole('status')).toHaveTextContent(label);
  });

  it('exposes reduced motion without removing status', () => {
    render(
      <VoiceOrb
        state="recording"
        amplitude={0.8}
        voiced
        reducedMotion
        label="Recording"
      />,
    );
    expect(screen.getByTestId('voice-orb')).toHaveAttribute('data-reduced-motion', 'true');
  });
});

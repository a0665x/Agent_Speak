import { render } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { ParticleField } from './ParticleField';

afterEach(() => {
  delete (window as typeof window & { AgentSpeakParticleField?: unknown }).AgentSpeakParticleField;
  document.querySelector('script[data-agent-speak-particles]')?.remove();
});

test('mounts the shared subtle particle engine and destroys it on unmount', () => {
  const destroy = vi.fn();
  const mount = vi.fn(() => ({ destroy }));
  (window as typeof window & { AgentSpeakParticleField: { mount: typeof mount } }).AgentSpeakParticleField = { mount };

  const view = render(<ParticleField profile="subtle" />);
  const canvas = view.getByTestId('particle-field');

  expect(canvas).toHaveAttribute('data-profile', 'subtle');
  expect(canvas).toHaveAttribute('aria-hidden', 'true');
  expect(mount).toHaveBeenCalledWith(canvas, { profile: 'subtle' });

  view.unmount();
  expect(destroy).toHaveBeenCalledTimes(1);
});

test('mounts when the shared browser asset becomes ready after React', () => {
  const destroy = vi.fn();
  const mount = vi.fn(() => ({ destroy }));
  const view = render(<ParticleField profile="subtle" />);

  const script = document.querySelector('script[data-agent-speak-particles]');
  expect(script).not.toBeNull();
  expect(script).toHaveAttribute('src', '/static/particle-field.js');

  (window as typeof window & { AgentSpeakParticleField: { mount: typeof mount } }).AgentSpeakParticleField = { mount };
  window.dispatchEvent(new Event('agent-speak-particles-ready'));

  expect(mount).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(destroy).toHaveBeenCalledTimes(1);
});

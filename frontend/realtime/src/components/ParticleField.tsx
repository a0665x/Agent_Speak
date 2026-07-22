import { useEffect, useRef } from 'react';

type ParticleController = { destroy: () => void };
type ParticleApi = {
  mount: (canvas: HTMLCanvasElement, options: { profile: 'hero' | 'subtle'; reducedMotion?: boolean }) => ParticleController;
};

declare global {
  interface Window {
    AgentSpeakParticleField?: ParticleApi;
  }
}

export function ParticleField({
  profile,
  reducedMotion,
}: {
  profile: 'hero' | 'subtle';
  reducedMotion?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let controller: ParticleController | undefined;
    const mount = () => {
      if (controller || !canvasRef.current || !window.AgentSpeakParticleField) return;
      const options: { profile: 'hero' | 'subtle'; reducedMotion?: boolean } = { profile };
      if (reducedMotion !== undefined) options.reducedMotion = reducedMotion;
      controller = window.AgentSpeakParticleField.mount(canvasRef.current, options);
    };
    mount();
    let script = document.querySelector<HTMLScriptElement>('script[data-agent-speak-particles]');
    if (!window.AgentSpeakParticleField && !script) {
      script = document.createElement('script');
      script.src = '/static/particle-field.js';
      script.defer = true;
      script.dataset.agentSpeakParticles = 'true';
      document.head.append(script);
    }
    script?.addEventListener('load', mount);
    window.addEventListener('agent-speak-particles-ready', mount);
    return () => {
      script?.removeEventListener('load', mount);
      window.removeEventListener('agent-speak-particles-ready', mount);
      controller?.destroy();
    };
  }, [profile, reducedMotion]);

  return (
    <canvas
      ref={canvasRef}
      className="ambient-particles"
      data-testid="particle-field"
      data-profile={profile}
      data-animated={reducedMotion ? 'false' : 'true'}
      aria-hidden="true"
    />
  );
}

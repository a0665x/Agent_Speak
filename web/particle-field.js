"use strict";

(function exposeParticleField(globalScope) {
  const PARTICLE_PROFILES = Object.freeze({
    hero: Object.freeze({ spacing: 25, maxParticles: 1400, opacity: 0.54, pointerRadius: 132, pointerForce: 1.05, spring: 0.042, damping: 0.84, float: 5.5, glow: 0.12 }),
    subtle: Object.freeze({ spacing: 36, maxParticles: 720, opacity: 0.25, pointerRadius: 104, pointerForce: 0.58, spring: 0.046, damping: 0.82, float: 3.2, glow: 0.055 }),
  });

  function profileFor(name) {
    return PARTICLE_PROFILES[name] || PARTICLE_PROFILES.subtle;
  }

  function createParticleLayout(width, height, profileName) {
    const profile = profileFor(profileName);
    const safeWidth = Math.max(1, Number(width) || 1);
    const safeHeight = Math.max(1, Number(height) || 1);
    const initialCount = Math.ceil(safeWidth / profile.spacing) * Math.ceil(safeHeight / profile.spacing);
    const spacing = profile.spacing * Math.max(1, Math.sqrt(initialCount / profile.maxParticles));
    const columns = Math.ceil(safeWidth / spacing) + 1;
    const rows = Math.ceil(safeHeight / spacing) + 1;
    const particles = [];

    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        const normalizedX = column / Math.max(1, columns - 1);
        const normalizedY = row / Math.max(1, rows - 1);
        const field = Math.sin(normalizedX * 9.2 + normalizedY * 2.4)
          + Math.cos(normalizedY * 8.1 - normalizedX * 2.7)
          + Math.sin((normalizedX + normalizedY) * 5.3) * 0.55;
        if (field < -0.72) continue;
        const depth = 0.24 + 0.76 * (0.5 + 0.5 * Math.sin(column * 0.37 + row * 0.71));
        const baseX = column * spacing + Math.sin(row * 0.61) * spacing * 0.16;
        const wave = Math.sin(normalizedX * 10.5 + row * 0.48) * 17 * depth
          + Math.cos(normalizedX * 4.2 - row * 0.31) * 8;
        const baseY = row * spacing + wave;
        particles.push({
          baseX,
          baseY,
          x: baseX,
          y: baseY,
          vx: 0,
          vy: 0,
          depth,
          radius: 0.5 + depth * 1.12,
          alpha: profile.opacity * (0.3 + depth * 0.7),
          phase: column * 0.39 + row * 0.57,
        });
      }
    }
    return particles.slice(0, profile.maxParticles);
  }

  function advanceParticle(particle, pointer, profile) {
    const dx = particle.x - pointer.x;
    const dy = particle.y - pointer.y;
    const distance = Math.hypot(dx, dy);
    if (pointer.active && distance > 0 && distance < profile.pointerRadius) {
      const force = (1 - distance / profile.pointerRadius) * profile.pointerForce * particle.depth;
      particle.vx += dx / distance * force;
      particle.vy += dy / distance * force;
    }
    particle.vx += (particle.baseX - particle.x) * profile.spring;
    particle.vy += (particle.baseY - particle.y) * profile.spring;
    particle.vx *= profile.damping;
    particle.vy *= profile.damping;
    particle.x += particle.vx;
    particle.y += particle.vy;
    return particle;
  }

  function stepParticle(source, pointer, profileName) {
    return advanceParticle({ ...source }, pointer, profileFor(profileName));
  }

  function mount(canvas, options) {
    if (!canvas || typeof canvas.getContext !== "function") return { destroy() {}, redraw() {}, particleCount: 0 };
    const settings = options || {};
    const profileName = settings.profile || canvas.dataset.profile || "subtle";
    const profile = profileFor(profileName);
    const context = canvas.getContext("2d");
    if (!context) return { destroy() {}, redraw() {}, particleCount: 0 };
    const windowRef = settings.window || globalScope;
    const documentRef = settings.document || windowRef.document;
    const media = windowRef.matchMedia?.("(prefers-reduced-motion: reduce)");
    const reducedMotion = settings.reducedMotion ?? media?.matches === true;
    const pointer = { x: 0, y: 0, active: false };
    let particles = [];
    let width = 1;
    let height = 1;
    let frame = 0;
    let resizeFrame = 0;
    let destroyed = false;

    function draw(time, animate) {
      frame = 0;
      if (destroyed) return;
      context.clearRect(0, 0, width, height);
      const glow = context.createRadialGradient(width * 0.58, height * 0.34, 0, width * 0.58, height * 0.34, Math.max(width, height) * 0.62);
      glow.addColorStop(0, `rgba(153, 177, 255, ${profile.glow})`);
      glow.addColorStop(0.48, `rgba(171, 139, 226, ${profile.glow * 0.36})`);
      glow.addColorStop(1, "rgba(5, 7, 12, 0)");
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);

      for (const particle of particles) {
        if (animate) advanceParticle(particle, pointer, profile);
        const floatY = animate ? Math.sin(time * 0.00042 + particle.phase) * profile.float * particle.depth : 0;
        const color = Math.round(194 + particle.depth * 22);
        context.beginPath();
        context.fillStyle = `rgba(${color}, ${Math.round(199 + particle.depth * 28)}, 255, ${particle.alpha})`;
        context.arc(particle.x, particle.y + floatY, particle.radius, 0, Math.PI * 2);
        context.fill();
      }
      if (!reducedMotion && documentRef?.visibilityState !== "hidden") {
        frame = windowRef.requestAnimationFrame((nextTime) => draw(nextTime, true));
      }
    }

    function resize() {
      resizeFrame = 0;
      if (frame) windowRef.cancelAnimationFrame(frame);
      frame = 0;
      width = Math.max(1, canvas.clientWidth || windowRef.innerWidth || 1);
      height = Math.max(1, canvas.clientHeight || windowRef.innerHeight || 1);
      const ratio = Math.min(2, Math.max(1, windowRef.devicePixelRatio || 1));
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      particles = createParticleLayout(width, height, profileName);
      draw(0, false);
    }

    function requestResize() {
      if (resizeFrame || destroyed) return;
      resizeFrame = windowRef.requestAnimationFrame(resize);
    }

    function handlePointer(event) {
      if (reducedMotion || event.pointerType === "touch") return;
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
    }

    function clearPointer() { pointer.active = false; }

    function handleVisibility() {
      if (documentRef.visibilityState === "hidden") {
        if (frame) windowRef.cancelAnimationFrame(frame);
        frame = 0;
      } else if (!reducedMotion && !frame) {
        frame = windowRef.requestAnimationFrame((time) => draw(time, true));
      }
    }

    windowRef.addEventListener("resize", requestResize, { passive: true });
    if (!reducedMotion) {
      windowRef.addEventListener("pointermove", handlePointer, { passive: true });
      windowRef.addEventListener("blur", clearPointer);
      documentRef?.addEventListener("pointerleave", clearPointer);
      documentRef?.addEventListener("visibilitychange", handleVisibility);
    }
    resize();

    return {
      get particleCount() { return particles.length; },
      redraw() { draw(0, false); },
      destroy() {
        destroyed = true;
        if (frame) windowRef.cancelAnimationFrame(frame);
        if (resizeFrame) windowRef.cancelAnimationFrame(resizeFrame);
        windowRef.removeEventListener("resize", requestResize);
        windowRef.removeEventListener("pointermove", handlePointer);
        windowRef.removeEventListener("blur", clearPointer);
        documentRef?.removeEventListener("pointerleave", clearPointer);
        documentRef?.removeEventListener("visibilitychange", handleVisibility);
      },
    };
  }

  const api = { PARTICLE_PROFILES, createParticleLayout, stepParticle, mount };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (globalScope) {
    globalScope.AgentSpeakParticleField = api;
    globalScope.dispatchEvent?.(new Event("agent-speak-particles-ready"));
  }
})(typeof window !== "undefined" ? window : globalThis);

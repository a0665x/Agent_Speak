"use strict";

(function exposeParticleField(globalScope) {
  const PARTICLE_PROFILES = Object.freeze({
    hero: Object.freeze({ spacing: 18, maxParticles: 2600, dormantOpacity: 0.012, activeOpacity: 0.9, pointerRadius: 180, pointerForce: 2.4, activeRadiusScale: 1.45, trailLifetimeMs: 4000, trailFloor: 0.02, spring: 0.05, damping: 0.82, float: 4.8 }),
    subtle: Object.freeze({ spacing: 20, maxParticles: 2200, dormantOpacity: 0.008, activeOpacity: 0.76, pointerRadius: 180, pointerForce: 2.4, activeRadiusScale: 1.45, trailLifetimeMs: 4000, trailFloor: 0.02, spring: 0.05, damping: 0.82, float: 4.2 }),
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
          radius: 0.72 + depth * 1.42,
          alpha: profile.dormantOpacity * (0.35 + depth * 0.65),
          energy: 0,
          phase: column * 0.39 + row * 0.57,
        });
      }
    }
    return particles.slice(0, profile.maxParticles);
  }

  function decayEnergy(energy, elapsedMs, profileName) {
    const profile = profileFor(profileName);
    const safeEnergy = Math.max(0, Math.min(1, Number(energy) || 0));
    const safeElapsed = Math.max(0, Number(elapsedMs) || 0);
    return safeEnergy * Math.pow(profile.trailFloor, safeElapsed / profile.trailLifetimeMs);
  }

  function particleAppearance(particle, profileName) {
    const profile = profileFor(profileName);
    const depth = Math.max(0, Math.min(1, Number(particle.depth) || 0));
    const energy = Math.max(0, Math.min(1, Number(particle.energy) || 0));
    const baseRadius = particle.radius || 0.72 + depth * 1.42;
    return {
      radius: baseRadius * (1 + energy * (profile.activeRadiusScale - 1)),
      alpha: (profile.dormantOpacity + energy * (profile.activeOpacity - profile.dormantOpacity)) * (0.35 + depth * 0.65),
    };
  }

  function applyTrailEnergy(particles, start, end, profile) {
    const segmentX = end.x - start.x;
    const segmentY = end.y - start.y;
    const segmentLength = Math.hypot(segmentX, segmentY);
    const steps = Math.max(1, Math.ceil(segmentLength / 12));
    const samples = [];
    for (let index = 0; index <= steps; index += 1) {
      const progress = index / steps;
      samples.push({ x: start.x + segmentX * progress, y: start.y + segmentY * progress });
    }

    for (const particle of particles) {
      let closest = null;
      let closestDistance = Infinity;
      for (const sample of samples) {
        const dx = particle.x - sample.x;
        const dy = particle.y - sample.y;
        const distance = Math.hypot(dx, dy);
        if (distance < closestDistance) {
          closest = { dx, dy };
          closestDistance = distance;
        }
      }
      if (!closest || closestDistance >= profile.pointerRadius) continue;
      const influence = 1 - closestDistance / profile.pointerRadius;
      particle.energy = Math.min(1, (particle.energy || 0) + influence * 0.9);
      let directionX = closest.dx;
      let directionY = closest.dy;
      let directionLength = closestDistance;
      if (directionLength < 0.001) {
        directionX = segmentLength > 0 ? -segmentY / segmentLength : 1;
        directionY = segmentLength > 0 ? segmentX / segmentLength : 0;
        directionLength = 1;
      }
      const force = influence * profile.pointerForce * particle.depth;
      particle.vx += directionX / directionLength * force;
      particle.vy += directionY / directionLength * force;
    }
    return particles;
  }

  function injectTrailEnergy(source, start, end, profileName) {
    return applyTrailEnergy(source.map((particle) => ({ ...particle })), start, end, profileFor(profileName));
  }

  function advanceParticle(particle, profile, elapsedMs) {
    particle.vx += (particle.baseX - particle.x) * profile.spring;
    particle.vy += (particle.baseY - particle.y) * profile.spring;
    particle.vx *= profile.damping;
    particle.vy *= profile.damping;
    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.energy = decayEnergy(particle.energy, elapsedMs, profile === PARTICLE_PROFILES.hero ? "hero" : "subtle");
    if (particle.energy < 0.0005) particle.energy = 0;
    return particle;
  }

  function stepParticle(source, pointer, profileName) {
    const profile = profileFor(profileName);
    const particle = { energy: 0, ...source };
    if (pointer.active) applyTrailEnergy([particle], pointer, pointer, profile);
    return advanceParticle(particle, profile, 16.67);
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
    let particles = [];
    let width = 1;
    let height = 1;
    let frame = 0;
    let resizeFrame = 0;
    let destroyed = false;
    let previousPointer = null;
    let previousTime = 0;

    function draw(time, animate) {
      frame = 0;
      if (destroyed) return;
      const elapsedMs = previousTime ? Math.min(50, Math.max(0, time - previousTime)) : 16.67;
      previousTime = time;
      context.clearRect(0, 0, width, height);

      for (const particle of particles) {
        if (animate) advanceParticle(particle, profile, elapsedMs);
        const appearance = particleAppearance(particle, profileName);
        const floatY = animate ? Math.sin(time * 0.00042 + particle.phase) * profile.float * particle.depth * particle.energy : 0;
        const color = Math.round(194 + particle.depth * 22 + particle.energy * 18);
        context.beginPath();
        context.fillStyle = `rgba(${color}, ${Math.round(199 + particle.depth * 28 + particle.energy * 8)}, 255, ${appearance.alpha})`;
        context.arc(particle.x, particle.y + floatY, appearance.radius, 0, Math.PI * 2);
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
      previousTime = 0;
      draw(0, false);
    }

    function requestResize() {
      if (resizeFrame || destroyed) return;
      resizeFrame = windowRef.requestAnimationFrame(resize);
    }

    function handlePointer(event) {
      if (reducedMotion || event.pointerType === "touch") return;
      const nextPointer = { x: event.clientX, y: event.clientY };
      if (previousPointer && Math.hypot(nextPointer.x - previousPointer.x, nextPointer.y - previousPointer.y) < 1) return;
      applyTrailEnergy(particles, previousPointer || nextPointer, nextPointer, profile);
      previousPointer = nextPointer;
    }

    function clearPointer() { previousPointer = null; }

    function handleVisibility() {
      if (documentRef.visibilityState === "hidden") {
        if (frame) windowRef.cancelAnimationFrame(frame);
        frame = 0;
      } else if (!reducedMotion && !frame) {
        previousTime = 0;
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

  const api = { PARTICLE_PROFILES, createParticleLayout, decayEnergy, injectTrailEnergy, particleAppearance, stepParticle, mount };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (globalScope) {
    globalScope.AgentSpeakParticleField = api;
    globalScope.dispatchEvent?.(new Event("agent-speak-particles-ready"));
  }
})(typeof window !== "undefined" ? window : globalThis);

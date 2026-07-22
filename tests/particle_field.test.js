"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  PARTICLE_PROFILES,
  createParticleLayout,
  decayEnergy,
  injectTrailEnergy,
  mount,
  particleAppearance,
  stepParticle,
} = require("../web/particle-field.js");

test("creates a deterministic particle wave within the profile budget", () => {
  const first = createParticleLayout(1440, 900, "hero");
  const second = createParticleLayout(1440, 900, "hero");

  assert.deepEqual(first, second);
  assert.ok(first.length > 300);
  assert.ok(first.length <= PARTICLE_PROFILES.hero.maxParticles);
  assert.ok(first.every((particle) => particle.radius > 0 && particle.alpha > 0));
});

test("uses cinematic density with a slightly quieter ASR peak", () => {
  const hero = createParticleLayout(1440, 900, "hero");
  const subtle = createParticleLayout(1440, 900, "subtle");

  assert.ok(hero.length > 1400);
  assert.ok(subtle.length > 720);
  assert.ok(subtle.length < hero.length);
  assert.ok(PARTICLE_PROFILES.subtle.activeOpacity < PARTICLE_PROFILES.hero.activeOpacity);
  assert.equal(PARTICLE_PROFILES.subtle.pointerForce, PARTICLE_PROFILES.hero.pointerForce);
});

test("energizes a continuous pointer segment and leaves distant particles dormant", () => {
  const particles = [
    { baseX: 50, baseY: 50, x: 50, y: 50, vx: 0, vy: 0, depth: 1, energy: 0 },
    { baseX: 500, baseY: 500, x: 500, y: 500, vx: 0, vy: 0, depth: 1, energy: 0 },
  ];
  const next = injectTrailEnergy(particles, { x: 0, y: 50 }, { x: 100, y: 50 }, "hero");

  assert.ok(next[0].energy > 0.7);
  assert.equal(next[1].energy, 0);
});

test("active particles grow, brighten, and fade near dark after four seconds", () => {
  const dormant = particleAppearance({ depth: 1, energy: 0 }, "hero");
  const active = particleAppearance({ depth: 1, energy: 1 }, "hero");

  assert.ok(active.radius >= dormant.radius * 1.35);
  assert.ok(active.alpha > dormant.alpha * 20);
  assert.ok(Math.abs(decayEnergy(1, 4000, "hero") - 0.02) < 0.002);
});

test("repels a nearby particle from the pointer without moving a distant one", () => {
  const source = { baseX: 100, baseY: 100, x: 100, y: 100, vx: 0, vy: 0, depth: 1, radius: 1, alpha: 1, phase: 0 };
  const near = stepParticle(source, { x: 92, y: 100, active: true }, "hero");
  const far = stepParticle(source, { x: 500, y: 500, active: true }, "hero");

  assert.ok(near.x > source.x);
  assert.equal(far.x, source.x);
  assert.equal(far.y, source.y);
});

test("springs a displaced particle smoothly toward its origin", () => {
  const displaced = { baseX: 100, baseY: 100, x: 150, y: 120, vx: 0, vy: 0, depth: 1, radius: 1, alpha: 1, phase: 0 };
  const next = stepParticle(displaced, { x: 0, y: 0, active: false }, "hero");

  assert.ok(next.x < displaced.x && next.x > displaced.baseX);
  assert.ok(next.y < displaced.y && next.y > displaced.baseY);
});

test("keeps a single animation loop after resize", () => {
  const listeners = new Map();
  const frames = new Map();
  let nextFrame = 1;
  const context = {
    clearRect() {}, fillRect() {}, beginPath() {}, arc() {}, fill() {}, setTransform() {},
    createRadialGradient() { return { addColorStop() {} }; },
  };
  const documentRef = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
  };
  const windowRef = {
    innerWidth: 800, innerHeight: 600, devicePixelRatio: 1, document: documentRef,
    matchMedia() { return { matches: false }; },
    addEventListener(type, listener) { listeners.set(type, listener); },
    removeEventListener(type) { listeners.delete(type); },
    requestAnimationFrame(callback) { const id = nextFrame++; frames.set(id, callback); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  };
  const canvas = { dataset: { profile: "hero" }, clientWidth: 800, clientHeight: 600, getContext() { return context; } };
  const controller = mount(canvas, { profile: "hero", window: windowRef, document: documentRef });

  assert.equal(frames.size, 1);
  listeners.get("resize")();
  assert.equal(frames.size, 2);
  const resizeFrame = Math.max(...frames.keys());
  const resize = frames.get(resizeFrame);
  frames.delete(resizeFrame);
  resize();
  assert.equal(frames.size, 1);

  controller.destroy();
});

test("draws one static frame and skips pointer listeners for reduced motion", () => {
  const listenerTypes = [];
  let frameRequests = 0;
  const context = {
    clearRect() {}, fillRect() {}, beginPath() {}, arc() {}, fill() {}, setTransform() {},
    createRadialGradient() { return { addColorStop() {} }; },
  };
  const documentRef = {
    visibilityState: "visible",
    addEventListener(type) { listenerTypes.push(type); },
    removeEventListener() {},
  };
  const windowRef = {
    innerWidth: 800, innerHeight: 600, devicePixelRatio: 1, document: documentRef,
    matchMedia() { return { matches: true }; },
    addEventListener(type) { listenerTypes.push(type); },
    removeEventListener() {},
    requestAnimationFrame() { frameRequests += 1; return frameRequests; },
    cancelAnimationFrame() {},
  };
  const canvas = { dataset: { profile: "hero" }, clientWidth: 800, clientHeight: 600, getContext() { return context; } };
  const controller = mount(canvas, { profile: "hero", window: windowRef, document: documentRef });

  assert.equal(frameRequests, 0);
  assert.deepEqual(listenerTypes, ["resize"]);
  controller.destroy();
});

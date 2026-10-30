'use client';

import * as THREE from 'three';

/* ------------------------------------------------------------------ */
/* Math helpers                                                        */
/* ------------------------------------------------------------------ */

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const lerp = THREE.MathUtils.lerp;
export const damp = THREE.MathUtils.damp;

export const easeInCubic = (t: number) => t * t * t;
export const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
export const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/** Slight overshoot — used for the verification checkmark pop-in. */
export const easeOutBack = (t: number) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

/** Deterministic PRNG so particle fields are stable across reloads. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Single timebase for the whole experience (seconds, monotonic). */
export const nowSec = () =>
  (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000;

/* ------------------------------------------------------------------ */
/* Procedural canvas textures (no image assets anywhere in this scene) */
/* ------------------------------------------------------------------ */

/**
 * Letter-spaced wordmark texture — used for the VOTEVAULT plaque label.
 * Drawn per-character for consistent tracking in every browser.
 */
export function makeLabelTexture(
  text: string,
  opts: { color?: string; fontSize?: number; tracking?: number; width?: number; height?: number } = {}
) {
  const {
    color = '#E9C982',
    fontSize = 58,
    tracking = 30,
    width = 1024,
    height = 128,
  } = opts;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return new THREE.Texture();

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = color;
  ctx.font = `700 ${fontSize}px Arial, 'Helvetica Neue', Helvetica, sans-serif`;
  ctx.textBaseline = 'middle';

  let total = 0;
  for (const ch of text) total += ctx.measureText(ch).width + tracking;
  total -= tracking;

  let x = (width - total) / 2;
  for (const ch of text) {
    ctx.fillText(ch, x, height / 2 + 2);
    x += ctx.measureText(ch).width + tracking;
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 8;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** Radial gradient texture — used for the checkmark halo and floor glow. */
export function makeRadialTexture(stops: Array<[number, string]>, size = 512) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return new THREE.Texture();

  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  for (const [offset, color] of stops) grad.addColorStop(offset, color);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

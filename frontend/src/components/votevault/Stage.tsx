'use client';

import { useMemo } from 'react';
import { Environment, Lightformer } from '@react-three/drei';
import { COLORS, LAYOUT } from './palette';
import { makeRadialTexture } from './utils';

/**
 * Cinematic stage dressing: near-black background with gentle fog,
 * warm key / champagne rim / amber fill lights, a fully procedural
 * environment (Lightformers — layered reflections for the glass and
 * metals, no HDRI assets), and a soft radial floor glow that grounds
 * the floating artifact.
 */
export function Stage() {
  const floorTex = useMemo(
    () =>
      makeRadialTexture([
        [0, '#2E1D0D'],
        [0.22, '#171008'],
        [0.5, '#0A0A0C'],
        [0.78, '#08090B'],
        [1, '#08090B'],
      ]),
    []
  );

  return (
    <>
      <color attach="background" args={[COLORS.obsidian]} />
      <fog attach="fog" args={[COLORS.obsidian, 11, 17.5]} />

      {/* ===== soft ambient base ===== */}
      <ambientLight intensity={0.16} color="#403A32" />

      {/* ===== warm cinematic key ===== */}
      <directionalLight position={[4.2, 5.2, 3.4]} intensity={1.5} color="#FFEFD6" />

      {/* ===== champagne rim from behind-left ===== */}
      <directionalLight position={[-5.2, 3.4, -4.4]} intensity={2.0} color="#F6EDDD" />

      {/* ===== low warm fill ===== */}
      <directionalLight position={[-2.6, -1.4, 4.2]} intensity={0.32} color="#E9C982" />

      {/* ===== procedural reflection environment ===== */}
      <Environment resolution={256} frames={1}>
        <color attach="background" args={['#0A0A0C']} />
        {/* tall warm strip, camera-left — the signature glass highlight */}
        <Lightformer form="rect" intensity={5} color="#FFD9A0" position={[-4, 2.2, 3]} scale={[2.2, 6, 1]} />
        {/* neutral vertical strip, camera-right */}
        <Lightformer form="rect" intensity={3.4} color="#FFF3E0" position={[4.4, 1.2, 2.4]} scale={[1.6, 5, 1]} />
        {/* soft overhead disc */}
        <Lightformer form="circle" intensity={2.2} color="#FFE7B8" position={[0, 6, 0]} scale={5} />
        {/* warm under-glow board */}
        <Lightformer form="rect" intensity={1.6} color="#E9C982" position={[0, -3.2, 2.4]} scale={[4, 1.4, 1]} />
        {/* back light seen through the glass from the front */}
        <Lightformer form="rect" intensity={1.2} color="#FFFFFF" position={[0, 1.4, -5.4]} scale={[3.4, 2.4, 1]} />
      </Environment>
    </>
  );
}

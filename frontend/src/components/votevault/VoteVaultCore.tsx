'use client';

import { Suspense } from 'react';
import * as THREE from 'three';
import { Canvas } from '@react-three/fiber';
import { Bloom, EffectComposer, Noise, ToneMapping, Vignette } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';
import { Director } from './Director';
import { GlassChamber } from './GlassChamber';
import { MetalBase } from './MetalBase';
import { BallotCard } from './BallotCard';
import { VerifiedCheckmark } from './VerifiedCheckmark';
import { OrbitalRings } from './OrbitalRings';
import { Particles } from './Particles';
import { Stage } from './Stage';

/**
 * VoteVault — Verifiable Ballot Core.
 *
 * A fully procedural React Three Fiber artifact: faceted glass chamber
 * (physically based transmission), sculpted black-metal pedestal with a
 * luminous gold chevron, sealed ballot card, amber insertion slot,
 * independent gold/silver orbital rings, floating geometric particles
 * and a cinematic warm lighting stage. No textures or image assets —
 * every surface, glow and wordmark is generated in code.
 *
 * Reusable: drop <VoteVaultCore /> into any React/Next.js page.
 */
export default function VoteVaultCore() {
  return (
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [0, 0.55, 8.8], fov: 34, near: 0.1, far: 60 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.NoToneMapping; // tone mapping happens in the composer
        gl.toneMappingExposure = 1.05;
      }}
      style={{ position: 'absolute', inset: 0 }}
    >
      <Suspense fallback={null}>
        <Director>
          <MetalBase />
          <GlassChamber />
          <BallotCard />
          <VerifiedCheckmark />
          <OrbitalRings />
        </Director>

        <Particles />
        <Stage />

        {/* Cinematic grade: restrained bloom on emissives, vignette, whisper of grain. */}
        <EffectComposer multisampling={8}>
          <Bloom mipmapBlur intensity={0.72} luminanceThreshold={1.0} luminanceSmoothing={0.25} radius={0.72} />
          <Vignette offset={0.22} darkness={0.72} eskil={false} />
          <Noise premultiply opacity={0.04} />
          <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        </EffectComposer>
      </Suspense>
    </Canvas>
  );
}

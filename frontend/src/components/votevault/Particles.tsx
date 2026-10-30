'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { COLORS } from './palette';
import { useVoteStore } from './store';
import { damp, mulberry32, nowSec } from './utils';

const COUNT = 76;

/* Shared materials — module-level singletons, animated in place. */
const GOLD_MAT = new THREE.MeshStandardMaterial({
  color: COLORS.gold,
  metalness: 1,
  roughness: 0.26,
  emissive: COLORS.amber,
  emissiveIntensity: 0,
});
const CHAMPAGNE_MAT = new THREE.MeshStandardMaterial({
  color: COLORS.champagne,
  metalness: 1,
  roughness: 0.38,
  emissive: COLORS.amber,
  emissiveIntensity: 0,
});
const SILVER_MAT = new THREE.MeshStandardMaterial({
  color: COLORS.glassHighlight,
  metalness: 1,
  roughness: 0.2,
});
const GRAPHITE_MAT = new THREE.MeshStandardMaterial({
  color: '#2B2B30',
  metalness: 0.9,
  roughness: 0.45,
});
const MATS = [GOLD_MAT, CHAMPAGNE_MAT, SILVER_MAT, GRAPHITE_MAT];

/* Shared geometries — module-level crystal singletons. */
const GEOS = [
  new THREE.OctahedronGeometry(0.055, 0),
  new THREE.TetrahedronGeometry(0.062, 0),
  new THREE.IcosahedronGeometry(0.045, 0),
  new THREE.BoxGeometry(0.11, 0.02, 0.035),
];

interface ParticleSpec {
  baseX: number;
  baseY: number;
  baseZ: number;
  ampX: number;
  ampY: number;
  ampZ: number;
  freqX: number;
  freqY: number;
  freqZ: number;
  phase: number;
  spin: [number, number, number];
  scale: number;
  kind: number;
}

/**
 * Floating geometric crystals all over the screen:
 * octahedra, tetrahedra, icosahedra and shards drifting across the entire
 * full-screen background in gold, champagne, silver and graphite.
 * Field responds to pointer parallax and lights up when ballots verify.
 */
export function Particles() {
  const group = useRef<THREE.Group>(null);
  const meshes = useRef<Array<THREE.Mesh | null>>([]);

  const specs = useMemo<ParticleSpec[]>(() => {
    const rand = mulberry32(1337);
    return Array.from({ length: COUNT }, () => ({
      // Spread across the full width and height of the screen
      baseX: (rand() - 0.5) * 15.5,
      baseY: -3.4 + rand() * 7.2,
      baseZ: -3.2 + rand() * 5.6,
      ampX: 0.05 + rand() * 0.16,
      ampY: 0.08 + rand() * 0.22,
      ampZ: 0.05 + rand() * 0.16,
      freqX: 0.2 + rand() * 0.55,
      freqY: 0.25 + rand() * 0.7,
      freqZ: 0.2 + rand() * 0.5,
      phase: rand() * Math.PI * 2,
      spin: [(rand() - 0.5) * 1.5, (rand() - 0.5) * 1.5, (rand() - 0.5) * 1.5],
      scale: 0.7 + rand() * 1.1,
      kind: Math.floor(rand() * 4),
    }));
  }, []);

  useFrame((state, dt) => {
    const t = nowSec();

    for (let i = 0; i < specs.length; i++) {
      const m = meshes.current[i];
      if (!m) continue;
      const p = specs[i];
      m.position.set(
        p.baseX + Math.sin(t * p.freqX + p.phase) * p.ampX,
        p.baseY + Math.sin(t * p.freqY + p.phase) * p.ampY,
        p.baseZ + Math.cos(t * p.freqZ + p.phase) * p.ampZ
      );
      m.rotation.x += dt * p.spin[0];
      m.rotation.y += dt * p.spin[1];
      m.rotation.z += dt * p.spin[2];
    }

    // Parallax field response across the full screen
    if (group.current) {
      group.current.rotation.y = damp(group.current.rotation.y, state.pointer.x * 0.14, 2, dt);
      group.current.rotation.x = damp(group.current.rotation.x, -state.pointer.y * 0.08, 2, dt);
    }

    // Golden particles glow while the core verifies
    const { phase } = useVoteStore.getState();
    const target = phase === 'verifying' ? 0.9 : phase === 'verified' ? 0.45 : 0;
    GOLD_MAT.emissiveIntensity = damp(GOLD_MAT.emissiveIntensity, target, 2.2, dt);
    CHAMPAGNE_MAT.emissiveIntensity = damp(CHAMPAGNE_MAT.emissiveIntensity, target * 0.6, 2.2, dt);
  });

  return (
    <group ref={group}>
      {specs.map((p, i) => (
        <mesh
          key={i}
          ref={(el) => {
            meshes.current[i] = el;
          }}
          geometry={GEOS[p.kind]}
          material={MATS[p.kind]}
          scale={p.scale}
        />
      ))}
    </group>
  );
}

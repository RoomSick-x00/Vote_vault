'use client';

import { useRef } from 'react';
import type * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { COLORS } from './palette';
import { useVoteStore } from './store';
import { nowSec } from './utils';

const TILT_1 = Math.PI / 2 - 0.4; // gold ring — 23° off horizontal
const TILT_2 = -(Math.PI / 2 - 0.55); // silver ring — 31.5° off horizontal, opposite lean

/**
 * Thin golden and silver orbital rings.
 *
 * Each ring precesses around the vertical at its own rate and carries
 * a small satellite bead orbiting along the ring — the two assemblies
 * are fully independent, and both briefly accelerate while the core
 * verifies a ballot.
 */
export function OrbitalRings() {
  const ring1 = useRef<THREE.Group>(null);
  const ring2 = useRef<THREE.Group>(null);
  const wobble1 = useRef<THREE.Group>(null);
  const wobble2 = useRef<THREE.Group>(null);
  const bead1 = useRef<THREE.Group>(null);
  const bead2 = useRef<THREE.Group>(null);

  useFrame(() => {
    const t = nowSec();
    const { phase } = useVoteStore.getState();
    const boost = phase === 'verifying' ? 2.6 : phase === 'verified' ? 1.7 : 1;

    if (ring1.current) ring1.current.rotation.y = t * 0.14 * boost + 0.3;
    if (ring2.current) ring2.current.rotation.y = -t * 0.095 * boost + 2.1;
    if (wobble1.current) wobble1.current.rotation.x = TILT_1 + Math.sin(t * 0.42) * 0.045;
    if (wobble2.current) wobble2.current.rotation.x = TILT_2 + Math.sin(t * 0.31 + 1.4) * 0.05;
    if (bead1.current) bead1.current.rotation.z = t * 0.52 * boost;
    if (bead2.current) bead2.current.rotation.z = -t * 0.36 * boost + 1.2;
  });

  return (
    <group>
      {/* ===== gold ring ===== */}
      <group ref={ring1}>
        <group ref={wobble1} rotation-x={TILT_1}>
          <mesh>
            <torusGeometry args={[2.16, 0.015, 16, 180]} />
            <meshStandardMaterial
              color={COLORS.gold}
              metalness={1}
              roughness={0.16}
              envMapIntensity={1.7}
              emissive={COLORS.amber}
              emissiveIntensity={0.06}
            />
          </mesh>
          <group ref={bead1}>
            <mesh position={[2.16, 0, 0]}>
              <sphereGeometry args={[0.047, 24, 24]} />
              <meshStandardMaterial
                color={COLORS.gold}
                metalness={1}
                roughness={0.2}
                emissive={COLORS.amber}
                emissiveIntensity={0.5}
              />
            </mesh>
          </group>
        </group>
      </group>

      {/* ===== silver ring ===== */}
      <group ref={ring2}>
        <group ref={wobble2} rotation-x={TILT_2}>
          <mesh>
            <torusGeometry args={[2.52, 0.011, 16, 200]} />
            <meshStandardMaterial
              color={COLORS.glassHighlight}
              metalness={1}
              roughness={0.11}
              envMapIntensity={1.5}
            />
          </mesh>
          <group ref={bead2}>
            <mesh position={[2.52, 0, 0]}>
              <sphereGeometry args={[0.034, 24, 24]} />
              <meshStandardMaterial color="#F5F5F5" metalness={1} roughness={0.14} envMapIntensity={1.6} />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
}

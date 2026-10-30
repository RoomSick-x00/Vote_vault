'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { RoundedBox } from '@react-three/drei';
import { COLORS, LAYOUT } from './palette';
import { BASE_PROFILE, makeChevronShape } from './geometry';
import { makeLabelTexture } from './utils';
import { useVoteStore } from './store';
import { damp, nowSec } from './utils';

/**
 * The sculpted black-metal pedestal.
 *
 * A lathe-turned profile (wide belly, inset waist with an emissive amber
 * strip, chamfered top plate) carries a small badge plaque on its front:
 * the luminous golden VoteVault chevron above a delicate VOTEVAULT
 * wordmark rendered to a procedural canvas texture.
 */
export function MetalBase() {
  const geo = useMemo(() => {
    const lathe = new THREE.LatheGeometry(BASE_PROFILE, 96);
    const chevron = new THREE.ExtrudeGeometry(makeChevronShape(), {
      depth: 0.05,
      curveSegments: 1,
      bevelEnabled: true,
      bevelThickness: 0.012,
      bevelSize: 0.012,
      bevelSegments: 2,
    });
    return { lathe, chevron };
  }, []);

  const labelTex = useMemo(() => makeLabelTexture('VOTEVAULT', { color: '#E9C982', fontSize: 62, tracking: 26 }), []);

  const stripMat = useRef<THREE.MeshStandardMaterial>(null);
  const chevMat = useRef<THREE.MeshStandardMaterial>(null);

  useFrame((_, dt) => {
    const t = nowSec();
    const { phase } = useVoteStore.getState();
    const stripTarget = phase === 'verifying' ? 3.6 : phase === 'verified' ? 2.6 : 1.35 + Math.sin(t * 1.9) * 0.2;
    if (stripMat.current) stripMat.current.emissiveIntensity = damp(stripMat.current.emissiveIntensity, stripTarget, 5, dt);
    if (chevMat.current) {
      const chevTarget = phase === 'verified' ? 3.4 : phase === 'verifying' ? 2.6 : 2.1 + Math.sin(t * 2.3) * 0.25;
      chevMat.current.emissiveIntensity = damp(chevMat.current.emissiveIntensity, chevTarget, 5, dt);
    }
  });

  return (
    <group position={[0, LAYOUT.baseBottomY, 0]}>
      {/* ===== sculpted body ===== */}
      <mesh geometry={geo.lathe}>
        <meshPhysicalMaterial
          color={COLORS.charcoal}
          metalness={0.92}
          roughness={0.3}
          clearcoat={0.55}
          clearcoatRoughness={0.28}
          envMapIntensity={1.55}
        />
      </mesh>

      {/* ===== emissive waist strip ===== */}
      <mesh position={[0, 0.325, 0]} rotation-x={Math.PI / 2}>
        <torusGeometry args={[0.812, 0.013, 10, 96]} />
        <meshStandardMaterial
          ref={stripMat}
          color="#241503"
          emissive={COLORS.amber}
          emissiveIntensity={1.35}
          metalness={0.2}
          roughness={0.5}
        />
      </mesh>

      {/* ===== badge plaque ===== */}
      <group position={[0, 0.36, 0.845]} rotation-x={-0.045}>
        {/* champagne back plate creates a thin metallic rim */}
        <RoundedBox args={[0.52, 0.4, 0.022]} radius={0.012} smoothness={3} position={[0, 0, -0.008]}>
          <meshStandardMaterial color={COLORS.champagne} metalness={1} roughness={0.28} envMapIntensity={1.3} />
        </RoundedBox>
        {/* dark front plate */}
        <RoundedBox args={[0.488, 0.368, 0.02]} radius={0.01} smoothness={3}>
          <meshPhysicalMaterial color="#101013" metalness={0.85} roughness={0.42} clearcoat={0.4} />
        </RoundedBox>

        {/* luminous golden chevron */}
        <mesh geometry={geo.chevron} scale={0.28} position={[0, 0.062, 0.014]}>
          <meshStandardMaterial
            ref={chevMat}
            color={COLORS.gold}
            emissive={COLORS.gold}
            emissiveIntensity={2.1}
            metalness={0.6}
            roughness={0.3}
          />
        </mesh>

        {/* VOTEVAULT wordmark */}
        <mesh position={[0, -0.105, 0.012]}>
          <planeGeometry args={[0.34, 0.0425]} />
          <meshStandardMaterial
            map={labelTex}
            emissiveMap={labelTex}
            emissive="#E9C982"
            emissiveIntensity={0.55}
            color="#FFFFFF"
            transparent
            roughness={0.4}
            metalness={0.1}
          />
        </mesh>
      </group>
    </group>
  );
}

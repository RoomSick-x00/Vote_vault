'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { COLORS, LAYOUT } from './palette';
import { makeCheckmarkShape } from './geometry';
import { makeRadialTexture, clamp01, easeOutBack, nowSec } from './utils';
import { useVoteStore } from './store';

/**
 * The glowing verification checkmark — the finale of the ceremony.
 *
 * A radiant golden check pops in above the insertion slot with an
 * elastic overshoot, floats gently, casts warm light back onto the
 * chamber and carries a soft additive halo sprite. It dissolves
 * again when the core resets.
 */
export function VerifiedCheckmark() {
  const group = useRef<THREE.Group>(null);
  const mat = useRef<THREE.MeshStandardMaterial>(null);
  const haloMat = useRef<THREE.SpriteMaterial>(null);
  const light = useRef<THREE.PointLight>(null);

  const checkGeo = useMemo(
    () =>
      new THREE.ExtrudeGeometry(makeCheckmarkShape(), {
        depth: 0.06,
        curveSegments: 1,
        bevelEnabled: true,
        bevelThickness: 0.016,
        bevelSize: 0.016,
        bevelSegments: 2,
      }),
    []
  );

  const haloTex = useMemo(
    () =>
      makeRadialTexture([
        [0, 'rgba(255, 214, 110, 0.95)'],
        [0.22, 'rgba(255, 157, 0, 0.5)'],
        [0.55, 'rgba(255, 157, 0, 0.12)'],
        [1, 'rgba(255, 157, 0, 0)'],
      ]),
    []
  );

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    const t = nowSec();
    const st = useVoteStore.getState();
    const { phase } = st;
    const pf = phase === 'verified' ? clamp01((t - st.phaseStart) / 2.8) : 0;
    const pr = phase === 'reset' ? clamp01((t - st.phaseStart) / 1.5) : 0;

    let scale = 0;
    let opacity = 0;
    let lightI = 0;
    let haloO = 0;

    if (phase === 'verified') {
      scale = Math.max(0.001, easeOutBack(clamp01(pf / 0.42)));
      opacity = clamp01(pf / 0.16);
      lightI = 7.5 * opacity * (0.86 + 0.14 * Math.sin(t * 3.1));
      haloO = 0.6 * opacity;
      g.rotation.y = Math.sin(t * 1.15) * 0.2 + (1 - clamp01(pf / 0.4)) * 0.7;
      g.position.y = LAYOUT.checkY + Math.sin(t * 1.4) * 0.05 + 0.12 * (1 - clamp01(pf / 0.5));
    } else if (phase === 'reset' && pr < 0.35) {
      const q = 1 - clamp01(pr / 0.35);
      scale = Math.max(0.001, q);
      opacity = q;
      lightI = 7.5 * q;
      haloO = 0.6 * q;
    }

    g.visible = scale > 0.012;
    g.scale.setScalar(scale);
    if (mat.current) {
      mat.current.opacity = opacity;
      mat.current.emissiveIntensity = 3.4 + Math.sin(t * 3.1) * 0.4;
    }
    if (haloMat.current) haloMat.current.opacity = haloO;
    if (light.current) light.current.intensity = lightI;
  });

  return (
    <group ref={group} position={[0, LAYOUT.checkY, 0]} visible={false}>
      {/* soft additive halo */}
      <sprite scale={[2.1, 2.1, 1]}>
        <spriteMaterial
          ref={haloMat}
          map={haloTex}
          color={COLORS.gold}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </sprite>

      {/* radiant golden check */}
      <mesh geometry={checkGeo} scale={0.82}>
        <meshStandardMaterial
          ref={mat}
          color={COLORS.gold}
          emissive="#FFC94D"
          emissiveIntensity={3.4}
          metalness={0.55}
          roughness={0.26}
          transparent
          opacity={0}
        />
      </mesh>

      <pointLight ref={light} color={COLORS.gold} intensity={0} distance={3.6} decay={2} />
    </group>
  );
}

'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { RoundedBox } from '@react-three/drei';
import { COLORS, LAYOUT } from './palette';
import { makeCheckmarkShape } from './geometry';
import { useVoteStore } from './store';
import { clamp01, easeInOutCubic, easeOutCubic, lerp, nowSec } from './utils';

/**
 * The white ballot card with its sculpted black checkmark.
 *
 * Rests inside the chamber with a gentle idle bob. During the casting
 * phase it straightens, rises through the glowing amber slot and
 * dissolves into the light; on reset it descends back to its cradle.
 */
export function BallotCard() {
  const group = useRef<THREE.Group>(null);

  const checkGeo = useMemo(
    () =>
      new THREE.ExtrudeGeometry(makeCheckmarkShape(), {
        depth: 0.024,
        curveSegments: 1,
        bevelEnabled: true,
        bevelThickness: 0.007,
        bevelSize: 0.007,
        bevelSegments: 2,
      }),
    []
  );

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    const t = nowSec();
    const st = useVoteStore.getState();
    const { phase } = st;
    const pc = phase === 'casting' ? clamp01((t - st.phaseStart) / 1.7) : 0;
    const pr = phase === 'reset' ? clamp01((t - st.phaseStart) / 1.5) : 0;

    let y = LAYOUT.ballotRestY + Math.sin(t * 1.05) * 0.035;
    let ry = -0.16 + Math.sin(t * 0.7) * 0.035;
    let rx = 0.02 + Math.sin(t * 0.83) * 0.012;
    let opacity = 1;

    if (phase === 'casting') {
      const e = easeInOutCubic(pc);
      y = lerp(LAYOUT.ballotRestY, LAYOUT.ballotExitY, e);
      // straighten early so the card clears the slit cleanly
      ry = lerp(-0.16, 0, clamp01(pc * 2.6));
      rx = lerp(0.02, 0, clamp01(pc * 2.6));
      y += Math.sin(t * 1.05) * 0.03 * (1 - pc);
      // dissolve into the light after clearing the slot
      opacity = pc < 0.78 ? 1 : 1 - clamp01((pc - 0.78) / 0.2);
    } else if (phase === 'verifying' || phase === 'verified') {
      opacity = 0;
      y = LAYOUT.ballotExitY;
    } else if (phase === 'reset') {
      // re-materialize above the slot, descend back into the cradle
      const e = easeOutCubic(clamp01(pr / 0.92));
      y = lerp(LAYOUT.ballotExitY - 0.28, LAYOUT.ballotRestY, e);
      ry = lerp(0, -0.16, e);
      rx = lerp(0, 0.02, e);
      opacity = clamp01(pr / 0.24) * (1 - clamp01((pr - 0.94) / 0.06));
    }

    g.position.y = y;
    g.rotation.set(rx, ry, Math.sin(t * 0.9) * 0.014 * (opacity > 0.5 ? 1 : 0));
    g.visible = opacity > 0.012;
    g.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh && mesh.material && 'opacity' in mesh.material) {
        mesh.material.opacity = opacity;
      }
    });
  });

  return (
    <group ref={group} position={[0, LAYOUT.ballotRestY, 0]}>
      {/* ===== paper ===== */}
      <RoundedBox args={[1.02, 1.42, 0.05]} radius={0.045} smoothness={4}>
        <meshPhysicalMaterial
          color={COLORS.ballot}
          roughness={0.42}
          clearcoat={0.35}
          clearcoatRoughness={0.5}
          sheen={0.5}
          sheenColor="#FFF6E4"
          transparent
        />
      </RoundedBox>

      {/* ===== checkbox frame ===== */}
      <group position={[0, 0.17, 0.026]}>
        <mesh position={[0, 0.205, 0]}>
          <boxGeometry args={[0.47, 0.014, 0.014]} />
          <meshStandardMaterial color="#26262A" roughness={0.45} metalness={0.2} transparent />
        </mesh>
        <mesh position={[0, -0.205, 0]}>
          <boxGeometry args={[0.47, 0.014, 0.014]} />
          <meshStandardMaterial color="#26262A" roughness={0.45} metalness={0.2} transparent />
        </mesh>
        <mesh position={[0.228, 0, 0]}>
          <boxGeometry args={[0.014, 0.424, 0.014]} />
          <meshStandardMaterial color="#26262A" roughness={0.45} metalness={0.2} transparent />
        </mesh>
        <mesh position={[-0.228, 0, 0]}>
          <boxGeometry args={[0.014, 0.424, 0.014]} />
          <meshStandardMaterial color="#26262A" roughness={0.45} metalness={0.2} transparent />
        </mesh>

        {/* ===== the black checkmark ===== */}
        <mesh geometry={checkGeo} scale={0.42} position={[0, 0, 0.008]}>
          <meshPhysicalMaterial
            color="#0B0B0D"
            roughness={0.22}
            metalness={0.15}
            clearcoat={0.9}
            clearcoatRoughness={0.18}
            envMapIntensity={1.2}
            transparent
          />
        </mesh>
      </group>

      {/* ===== faint printed lines ===== */}
      <mesh position={[-0.06, -0.36, 0.027]}>
        <boxGeometry args={[0.54, 0.017, 0.008]} />
        <meshStandardMaterial color="#D9D5C6" roughness={0.6} transparent />
      </mesh>
      <mesh position={[0.02, -0.44, 0.027]}>
        <boxGeometry args={[0.38, 0.017, 0.008]} />
        <meshStandardMaterial color="#DDD9CB" roughness={0.6} transparent />
      </mesh>
      <mesh position={[-0.02, -0.52, 0.027]}>
        <boxGeometry args={[0.3, 0.017, 0.008]} />
        <meshStandardMaterial color="#DBD7C9" roughness={0.6} transparent />
      </mesh>

      {/* ===== header accent ===== */}
      <mesh position={[0.05, 0.6, 0.027]}>
        <boxGeometry args={[0.3, 0.045, 0.01]} />
        <meshStandardMaterial color="#C9A86A" roughness={0.45} metalness={0.35} transparent />
      </mesh>
    </group>
  );
}

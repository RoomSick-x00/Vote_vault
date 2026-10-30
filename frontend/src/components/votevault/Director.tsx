'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { LAYOUT } from './palette';
import { PHASE_DURATION, useVoteStore } from './store';
import { clamp01, damp, easeOutCubic, nowSec } from './utils';
import { useUIStore } from '../../store/ui';

/**
 * The Director owns everything global:
 *
 * - the voting state machine (casting → verifying → verified → reset)
 * - the artifact rig: positions the 3D vault object on the right side of the screen
 *   on desktop viewports (centered on mobile), slow float, subtle sway, and smooth pointer response
 * - a cinematic camera: responsive framing with gentle dolly-in while verifying
 */
export function Director({ children }: { children: React.ReactNode }) {
  const rig = useRef<THREE.Group>(null);

  const reducedMotion = useMemo(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    []
  );

  useFrame((state, dt) => {
    const t = nowSec();

    /* ---------- phase machine ---------- */
    const st = useVoteStore.getState();
    const dur = PHASE_DURATION[st.phase];
    if (isFinite(dur) && t - st.phaseStart >= dur) st.advance();

    /* ---------- artifact rig (Vault on right side on desktop) ---------- */
    const g = rig.current;
    const aspect = state.size.width / Math.max(1, state.size.height);
    const isDesktop = aspect > 1.05;

    if (g) {
      const intro = easeOutCubic(clamp01((t - 0.15) / 1.6));
      const motionEnabled = useUIStore.getState().motionEnabled;
      const amp = (!motionEnabled || reducedMotion) ? 0.22 : 1;

      // Position the 3D vault on the right side on desktop
      const targetX = isDesktop ? 2.5 : 0;
      g.position.x = damp(g.position.x, targetX, 2.4, dt);

      g.position.y =
        LAYOUT.groupY + Math.sin(t * 0.55) * 0.075 * amp * intro - (1 - intro) * 0.3;

      const px = state.pointer.x;
      const py = state.pointer.y;
      g.rotation.y = damp(g.rotation.y, px * 0.4 * amp + Math.sin(t * 0.2) * 0.05, 2.4, dt);
      g.rotation.x = damp(g.rotation.x, -py * 0.17 * amp + Math.sin(t * 0.31) * 0.02, 2.4, dt);
      g.scale.setScalar(0.94 + 0.06 * intro);
    }

    /* ---------- camera ---------- */
    const cam = state.camera as THREE.PerspectiveCamera;
    const halfTan = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
    const baseZ = aspect < 0.95 ? THREE.MathUtils.clamp(3.15 / (halfTan * aspect), 9.4, 14.5) : 8.8;

    const phase = useVoteStore.getState().phase;
    const intimate = phase === 'verifying' || phase === 'verified';
    const targetZ = baseZ - (intimate ? 0.5 : 0);
    const targetY = 0.55 + (intimate ? 0.3 : 0);

    cam.position.z = damp(cam.position.z, targetZ, 2, dt);
    cam.position.y = damp(cam.position.y, targetY, 2, dt);
    cam.position.x = damp(cam.position.x, state.pointer.x * 0.35, 2.2, dt);
    cam.lookAt(isDesktop ? 0.6 : 0, 0.74, 0);
  });

  return <group ref={rig}>{children}</group>;
}

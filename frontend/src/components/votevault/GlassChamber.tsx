'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { MeshTransmissionMaterial } from '@react-three/drei';
import { COLORS, LAYOUT } from './palette';
import {
  extrudeVertical,
  octagonPoints,
  ringGeometryVertical,
  roundedRectPoints,
  shapeFromPoints,
} from './geometry';
import { useVoteStore } from './store';
import { clamp01, damp, easeInOutCubic, lerp, nowSec } from './utils';

/**
 * Ballot travel height while casting (shared with the slot flare logic).
 * Mirrors the exact path used by <BallotCard />.
 */
export function ballotTravelY(progressCasting: number): number {
  return lerp(LAYOUT.ballotRestY, LAYOUT.ballotExitY, easeInOutCubic(progressCasting));
}

/**
 * The faceted transparent glass chamber — the heart of the artifact.
 *
 * Everything is procedural: the body is an extruded elongated octagon with
 * thick beveled ends, rendered with a physically based transmission material
 * (refraction, chromatic aberration, warm attenuation and a backside pass for
 * layered double-refraction). The top carries a machined cap with a glowing
 * amber insertion slit; champagne trims trace the bevels; a warm emissive
 * puck lights the ballot from below; an additive interior shell lets the
 * chamber "ignite" with gold during verification, swept by a scan ring.
 */
export function GlassChamber() {
  /* ---------------- geometry (all procedural) ---------------- */
  const geo = useMemo(() => {
    const body = extrudeVertical(shapeFromPoints(octagonPoints(1.5, 1.05, 0.3)), {
      depth: 2.5,
      bevelThickness: 0.14,
      bevelSize: 0.12,
      bevelSegments: 2,
    });

    const glow = body.clone().scale(0.985, 0.99, 0.985);

    // Champagne trim rings hugging the top / bottom bevels of the glass.
    const trim = ringGeometryVertical(
      octagonPoints(1.66, 1.21, 0.34),
      octagonPoints(1.55, 1.1, 0.3),
      { depth: 0.075, bevelThickness: 0.018, bevelSize: 0.018, bevelSegments: 1 }
    );

    // Machined cap: octagon plate with a rounded-rect slit for the ballot.
    const capShape = shapeFromPoints(octagonPoints(1.58, 1.13, 0.32));
    capShape.holes.push(new THREE.Path(roundedRectPoints(1.14, 0.17, 0.05)));
    const cap = extrudeVertical(capShape, {
      depth: 0.14,
      bevelThickness: 0.022,
      bevelSize: 0.022,
      bevelSegments: 1,
    });

    // Thin champagne frame around the cap.
    const capTrim = ringGeometryVertical(
      octagonPoints(1.63, 1.18, 0.33),
      octagonPoints(1.55, 1.1, 0.31),
      { depth: 0.05, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 1 }
    );

    // Verification scan ring — hugs the chamber cross-section.
    const scan = ringGeometryVertical(
      octagonPoints(1.74, 1.28, 0.35),
      octagonPoints(1.6, 1.14, 0.31),
      { depth: 0.02, bevelThickness: 0, bevelSize: 0 }
    );

    return { body, glow, trim, cap, capTrim, scan };
  }, []);

  /* ---------------- animated material refs ---------------- */
  const slotMat = useRef<THREE.MeshStandardMaterial>(null);
  const slotLight = useRef<THREE.PointLight>(null);
  const glowMat = useRef<THREE.MeshBasicMaterial>(null);
  const scanMat = useRef<THREE.MeshBasicMaterial>(null);
  const scanRef = useRef<THREE.Mesh>(null);
  const underMat = useRef<THREE.MeshStandardMaterial>(null);
  const underLight = useRef<THREE.PointLight>(null);
  const trimMat = useRef<THREE.MeshStandardMaterial>(null);
  const gapMat = useRef<THREE.MeshStandardMaterial>(null);

  useFrame((_, dt) => {
    const t = nowSec();
    const { phase } = useVoteStore.getState();
    const pc = phase === 'casting' ? clamp01((t - useVoteStore.getState().phaseStart) / 1.7) : 0;
    const pv = phase === 'verifying' ? clamp01((t - useVoteStore.getState().phaseStart) / 2.3) : 0;
    const pf = phase === 'verified' ? clamp01((t - useVoteStore.getState().phaseStart) / 2.8) : 0;

    /* --- insertion slot: soft idle pulse, hard flare as the ballot passes --- */
    let slotI = 1.55 + Math.sin(t * 2.1) * 0.3;
    let slotL = 2.0;
    if (phase === 'casting') {
      const by = ballotTravelY(pc);
      if (by > LAYOUT.slotY - 0.34 && by < LAYOUT.slotY + 0.5) {
        slotI = 6.8;
        slotL = 16;
      }
    } else if (phase === 'verifying') {
      slotI = 3.1 + Math.sin(t * 9) * 0.7;
      slotL = 6;
    } else if (phase === 'verified') {
      slotI = 2.6 + Math.sin(t * 1.6) * 0.35;
      slotL = 4;
    }
    if (slotMat.current) slotMat.current.emissiveIntensity = damp(slotMat.current.emissiveIntensity, slotI, 10, dt);
    if (slotLight.current) slotLight.current.intensity = damp(slotLight.current.intensity, slotL, 10, dt);

    /* --- warm light source beneath the ballot --- */
    const underBase = 2.3 + Math.sin(t * 1.7) * 0.25;
    let underI = underBase;
    let lightI = 6.5 + Math.sin(t * 1.7) * 0.8;
    if (phase === 'casting') {
      underI = 3.4;
      lightI = 9;
    } else if (phase === 'verifying') {
      underI = 4.6 + pv * 1.2;
      lightI = 26 + Math.sin(t * 12) * 5;
    } else if (phase === 'verified') {
      underI = 3.8;
      lightI = 15;
    }
    if (underMat.current) underMat.current.emissiveIntensity = damp(underMat.current.emissiveIntensity, underI, 6, dt);
    if (underLight.current) underLight.current.intensity = damp(underLight.current.intensity, lightI, 6, dt);

    /* --- golden interior illumination --- */
    let glowO = 0.045 + Math.sin(t * 1.2) * 0.012;
    if (phase === 'verifying') glowO = 0.05 + easeInOutCubic(pv) * 0.3 * (0.8 + 0.2 * Math.sin(t * 14));
    else if (phase === 'verified') glowO = 0.16 + Math.sin(t * 2) * 0.02;
    else if (phase === 'reset') glowO = 0.16 * (1 - clamp01((t - useVoteStore.getState().phaseStart) / 0.9));
    if (glowMat.current) glowMat.current.opacity = damp(glowMat.current.opacity, glowO, 8, dt);

    /* --- champagne trims brighten with the ceremony --- */
    const trimTarget = phase === 'verifying' ? 1.7 : phase === 'verified' ? 1.1 : 0.5;
    if (trimMat.current) trimMat.current.emissiveIntensity = damp(trimMat.current.emissiveIntensity, trimTarget, 5, dt);
    if (gapMat.current) {
      const gapTarget = phase === 'verifying' ? 3.4 : phase === 'verified' ? 2.2 : 1.8;
      gapMat.current.emissiveIntensity = damp(gapMat.current.emissiveIntensity, gapTarget, 5, dt);
    }

    /* --- verification scan ring sweeping up the chamber --- */
    if (scanRef.current && scanMat.current) {
      if (phase === 'verifying') {
        const e = easeInOutCubic(pv);
        scanRef.current.position.y = lerp(-1.28, 1.3, e);
        scanMat.current.opacity = Math.sin(Math.PI * pv) * 0.9;
        scanRef.current.visible = true;
      } else if (scanMat.current.opacity > 0.01) {
        scanMat.current.opacity = damp(scanMat.current.opacity, 0, 12, dt);
      } else {
        scanRef.current.visible = false;
      }
    }
  });

  const startVote = () => useVoteStore.getState().start();

  return (
    <group>
      {/* ===== faceted glass body ===== */}
      <mesh
        geometry={geo.body}
        onClick={(e) => {
          e.stopPropagation();
          startVote();
        }}
        onPointerOver={() => {
          if (useVoteStore.getState().phase === 'idle') document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'auto';
        }}
      >
        <MeshTransmissionMaterial
          samples={6}
          resolution={1024}
          backside
          backsideResolution={512}
          backsideThickness={0.42}
          transmission={1}
          thickness={1.45}
          roughness={0.07}
          ior={1.52}
          chromaticAberration={0.05}
          anisotropy={0.12}
          distortion={0.14}
          distortionScale={0.4}
          temporalDistortion={0.06}
          attenuationDistance={2.4}
          attenuationColor={COLORS.glassTint}
          color="#FFFFFF"
        />
      </mesh>

      {/* ===== additive interior glow shell ===== */}
      <mesh geometry={geo.glow} renderOrder={2}>
        <meshBasicMaterial
          ref={glowMat}
          color={COLORS.amber}
          side={THREE.BackSide}
          transparent
          opacity={0.045}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ===== warm light source beneath the ballot ===== */}
      <mesh position={[0, -1.12, 0]}>
        <cylinderGeometry args={[0.42, 0.47, 0.07, 48]} />
        <meshStandardMaterial
          ref={underMat}
          color="#2A1B08"
          emissive={COLORS.amber}
          emissiveIntensity={2.3}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      <pointLight
        ref={underLight}
        position={[0, -0.82, 0]}
        color={COLORS.warmLight}
        intensity={6.5}
        distance={4.4}
        decay={2}
      />

      {/* ===== champagne bevel trims (warm emissive strips) ===== */}
      <mesh geometry={geo.trim} position={[0, 1.29, 0]}>
        <meshStandardMaterial
          ref={trimMat}
          color={COLORS.champagne}
          metalness={1}
          roughness={0.24}
          emissive={COLORS.amber}
          emissiveIntensity={0.5}
        />
      </mesh>
      <mesh geometry={geo.trim} position={[0, -1.29, 0]}>
        <meshStandardMaterial
          color={COLORS.champagne}
          metalness={1}
          roughness={0.24}
          emissive={COLORS.amber}
          emissiveIntensity={0.5}
        />
      </mesh>

      {/* ===== luminous gap ring between base and chamber ===== */}
      <mesh position={[0, LAYOUT.gapRingY, 0]} rotation-x={Math.PI / 2}>
        <torusGeometry args={[0.66, 0.02, 12, 72]} />
        <meshStandardMaterial
          ref={gapMat}
          color="#1D1206"
          emissive={COLORS.amber}
          emissiveIntensity={1.8}
          metalness={0.2}
          roughness={0.5}
        />
      </mesh>
      <pointLight position={[0, LAYOUT.gapRingY, 0]} color={COLORS.amber} intensity={2.2} distance={1.9} decay={2} />

      {/* ===== insertion slot cap ===== */}
      <group position={[0, LAYOUT.capY, 0]}>
        <mesh geometry={geo.cap}>
          <meshPhysicalMaterial
            color={COLORS.charcoal}
            metalness={0.95}
            roughness={0.32}
            clearcoat={0.6}
            clearcoatRoughness={0.3}
            envMapIntensity={1.2}
          />
        </mesh>
        <mesh geometry={geo.capTrim} position={[0, -0.045, 0]}>
          <meshStandardMaterial color={COLORS.champagne} metalness={1} roughness={0.22} />
        </mesh>
        {/* the glowing amber slit */}
        <mesh position={[0, 0.052, 0]}>
          <boxGeometry args={[1.06, 0.045, 0.085]} />
          <meshStandardMaterial
            ref={slotMat}
            color="#331F05"
            emissive={COLORS.amber}
            emissiveIntensity={1.55}
            metalness={0}
            roughness={0.35}
          />
        </mesh>
        <pointLight ref={slotLight} position={[0, 0.2, 0]} color={COLORS.amber} intensity={2} distance={2.8} decay={2} />
      </group>

      {/* ===== verification scan ring ===== */}
      <mesh ref={scanRef} geometry={geo.scan} visible={false} renderOrder={3}>
        <meshBasicMaterial
          ref={scanMat}
          color={COLORS.gold}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

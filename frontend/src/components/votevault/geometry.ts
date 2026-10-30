'use client';

import * as THREE from 'three';

/* ------------------------------------------------------------------ */
/* Cross-sections                                                      */
/* ------------------------------------------------------------------ */

/**
 * Elongated octagon (rectangle with chamfered corners) — the faceted
 * cross-section of the glass chamber, cap and trim rings.
 */
export function octagonPoints(w: number, d: number, c: number): THREE.Vector2[] {
  const hw = w / 2;
  const hd = d / 2;
  return [
    new THREE.Vector2(-hw + c, -hd),
    new THREE.Vector2(hw - c, -hd),
    new THREE.Vector2(hw, -hd + c),
    new THREE.Vector2(hw, hd - c),
    new THREE.Vector2(hw - c, hd),
    new THREE.Vector2(-hw + c, hd),
    new THREE.Vector2(-hw, hd - c),
    new THREE.Vector2(-hw, -hd + c),
  ];
}

export function shapeFromPoints(pts: THREE.Vector2[]): THREE.Shape {
  const shape = new THREE.Shape();
  pts.forEach((p, i) => (i === 0 ? shape.moveTo(p.x, p.y) : shape.lineTo(p.x, p.y)));
  shape.closePath();
  return shape;
}

/** Rounded rectangle centered on the origin — used for the ballot slit. */
export function roundedRectPoints(w: number, h: number, r: number, seg = 6): THREE.Vector2[] {
  const pts: THREE.Vector2[] = [];
  const hw = w / 2;
  const hh = h / 2;
  const corner = (cx: number, cy: number, a0: number) => {
    for (let i = 0; i <= seg; i++) {
      const a = a0 + (i / seg) * (Math.PI / 2);
      pts.push(new THREE.Vector2(cx + Math.cos(a) * r, cy + Math.sin(a) * r));
    }
  };
  corner(-hw + r, -hh + r, Math.PI);
  corner(hw - r, -hh + r, -Math.PI / 2);
  corner(hw - r, hh - r, 0);
  corner(-hw + r, hh - r, Math.PI / 2);
  return pts;
}

/* ------------------------------------------------------------------ */
/* Extrusion builders                                                  */
/* ------------------------------------------------------------------ */

type ExtrudeOpts = {
  depth: number;
  bevelThickness?: number;
  bevelSize?: number;
  bevelSegments?: number;
};

/**
 * Extrudes a shape along +Z, then rotates it so the extrusion axis
 * points up (+Y) and the geometry is vertically centered.
 */
export function extrudeVertical(shape: THREE.Shape, opts: ExtrudeOpts): THREE.ExtrudeGeometry {
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: opts.depth,
    curveSegments: 1,
    bevelEnabled: (opts.bevelThickness ?? 0) > 0,
    bevelThickness: opts.bevelThickness ?? 0,
    bevelSize: opts.bevelSize ?? 0,
    bevelSegments: opts.bevelSegments ?? 1,
  });
  geo.rotateX(-Math.PI / 2);
  geo.computeBoundingBox();
  const bb = geo.boundingBox!;
  geo.translate(-(bb.max.x + bb.min.x) / 2, -(bb.max.y + bb.min.y) / 2, -(bb.max.z + bb.min.z) / 2);
  return geo;
}

/**
 * Flat ring (outline shape with a hole), extruded vertically.
 * Used for the champagne trims and the verification scan ring.
 */
export function ringGeometryVertical(
  outerPts: THREE.Vector2[],
  innerPts: THREE.Vector2[],
  opts: ExtrudeOpts
): THREE.ExtrudeGeometry {
  const shape = shapeFromPoints(outerPts);
  shape.holes.push(new THREE.Path(innerPts));
  return extrudeVertical(shape, opts);
}

/* ------------------------------------------------------------------ */
/* Signature shapes                                                    */
/* ------------------------------------------------------------------ */

/**
 * Sculpted checkmark (the ballot mark and the verification mark).
 * Built as a mitered offset polygon of a two-segment stroke.
 */
export function makeCheckmarkShape(): THREE.Shape {
  const pts: Array<[number, number]> = [
    [0.0234, 0.4434],
    [0.406, 0.061],
    [1.012, 0.799],
    [0.888, 0.901],
    [0.394, 0.2992],
    [0.1366, 0.5566],
  ];
  const cx = 0.5177; // centroid-ish so scaling feels centered
  const cy = 0.481;
  const shape = new THREE.Shape();
  pts.forEach(([x, y], i) => {
    const X = x - cx;
    const Y = y - cy;
    if (i === 0) shape.moveTo(X, Y);
    else shape.lineTo(X, Y);
  });
  shape.closePath();
  return shape;
}

/**
 * The VoteVault chevron — an upward mitered angle stroke.
 */
export function makeChevronShape(): THREE.Shape {
  const pts: Array<[number, number]> = [
    [-0.6136, -0.2436],
    [0, 0.4481],
    [0.6136, -0.2436],
    [0.4864, -0.3564],
    [0, 0.1919],
    [-0.4864, -0.3564],
  ];
  const shape = new THREE.Shape();
  pts.forEach(([x, y], i) => {
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  shape.closePath();
  return shape;
}

/**
 * Lathe profile of the sculpted pedestal: wide belly, inset waist
 * (carrying the emissive strip), chamfered top plate.
 */
export const BASE_PROFILE: THREE.Vector2[] = [
  new THREE.Vector2(0.0, 0.0),
  new THREE.Vector2(0.58, 0.0),
  new THREE.Vector2(0.85, 0.012),
  new THREE.Vector2(0.965, 0.055),
  new THREE.Vector2(1.02, 0.135),
  new THREE.Vector2(0.995, 0.21),
  new THREE.Vector2(0.875, 0.275),
  new THREE.Vector2(0.79, 0.325),
  new THREE.Vector2(0.845, 0.375),
  new THREE.Vector2(0.93, 0.45),
  new THREE.Vector2(0.945, 0.515),
  new THREE.Vector2(0.875, 0.575),
  new THREE.Vector2(0.795, 0.615),
  new THREE.Vector2(0.775, 0.66),
  new THREE.Vector2(0.75, 0.685),
  new THREE.Vector2(0.0, 0.7),
];

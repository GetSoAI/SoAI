/* SoAI - About page controllers contracts [frontend/assets/ts/pages/about/controllers/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Particle } from '@pages/about/controllers/easterEggParticles.ts';

export interface AnimationHost {
    getScene(): HTMLElement | null;
    getOrb(): HTMLElement | null;
    getParticleCanvas(): HTMLCanvasElement | null;
    getGlowElement(): HTMLElement | null;
    onCelebrationComplete(): void;
}

export type AnimationPhase = 'idle' | 'hover' | 'exploding' | 'reassembling' | 'celebrating';

export interface OrbitRingConfig {
    minRadius: number;
    maxRadius: number;
    minSpeed: number;
    maxSpeed: number;
}

export interface ColorPalette {
    particleColors: string[];
    glowColor: string;
    orbGradient: string;
}

export interface AnimationState {
    phase: AnimationPhase;
    particles: Particle[];
    orbRotation: { x: number; y: number };
    cursorPosition: { x: number; y: number } | null;
    animationFrame: number | null;
    phaseStartTime: number;
    starfieldElement: HTMLElement | null;
    lastMouseMoveTime: number;
    paletteIndex: number;
    rippleStartTime: number | null;
}

/* SoAI - About page easter egg particles [frontend/assets/ts/pages/about/controllers/easterEggParticles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';

export interface ParticleConfig {
    count: number;
    minSize: number;
    maxSize: number;
    colors: readonly string[];
}

export interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    size: number;
    color: string;
    targetX: number;
    targetY: number;
    orbitOffset: number;
    orbitSpeed: number;
    orbitRadius: number;
    opacity: number;
    scale: number;
    pulseSpeed: number;
    rippleDelay: number;
    rippleRecolored: boolean;
}

export interface RepulsionVector {
    vx: number;
    vy: number;
}

interface ViewportBreakpoints {
    readonly medium: 768;
    readonly small: 480;
}

interface ParticleMultipliers {
    readonly large: 1;
    readonly medium: 0.65;
    readonly small: 0.4;
}

const VIEWPORT_BREAKPOINTS: ViewportBreakpoints = Object.freeze({ medium: 768, small: 480 });
const PARTICLE_MULTIPLIERS: ParticleMultipliers = Object.freeze({ large: 1, medium: 0.65, small: 0.4 });

export const randomInRange = (min: number, max: number): number => Math.random() * (max - min) + min;

const randomFromArray = <T>(array: readonly T[]): T => {
    const index = Math.floor(Math.random() * array.length);
    const value = array[index];
    if (value === undefined) {
        throw new Error('Array must not be empty');
    }
    return value;
};

export const getResponsiveParticleCount = (scope: Element, baseCount: number): number => {
    const width = measureLayoutViewport(scope).width;
    if (width <= VIEWPORT_BREAKPOINTS.small) {
        return Math.floor(baseCount * PARTICLE_MULTIPLIERS.small);
    }
    if (width <= VIEWPORT_BREAKPOINTS.medium) {
        return Math.floor(baseCount * PARTICLE_MULTIPLIERS.medium);
    }
    return Math.floor(baseCount * PARTICLE_MULTIPLIERS.large);
};

export const createParticle = (config: ParticleConfig): Particle => {
    return {
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        size: randomInRange(config.minSize, config.maxSize),
        color: randomFromArray(config.colors),
        targetX: 0,
        targetY: 0,
        orbitOffset: randomInRange(0, Math.PI * 2),
        orbitSpeed: randomInRange(0.3, 1.2),
        orbitRadius: randomInRange(50, 100),
        opacity: 1,
        scale: 1,
        pulseSpeed: randomInRange(1.5, 4.0),
        rippleDelay: 0,
        rippleRecolored: true
    };
};

export const calculateRepulsion = (particle: Particle, cursorX: number, cursorY: number, strength: number, radius: number): RepulsionVector => {
    const dx = particle.x - cursorX;
    const dy = particle.y - cursorY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance >= radius || distance < 0.1) {
        return { vx: 0, vy: 0 };
    }
    const force = (1 - distance / radius) * strength;
    const angle = Math.atan2(dy, dx);
    return {
        vx: Math.cos(angle) * force,
        vy: Math.sin(angle) * force
    };
};

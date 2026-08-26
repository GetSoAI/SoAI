/* SoAI - About page controllers effects [frontend/assets/ts/pages/about/controllers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { AMBIENT_PARTICLE_BASE, COLOR_PALETTES, ORBIT_RINGS, RIPPLE_WAVE_MS_PER_PX, STARFIELD_COUNT } from '@pages/about/controllers/constants.ts';
import { getPaletteByIndex } from '@pages/about/controllers/animationHelpers.ts';
import { createStarfield } from '@pages/about/controllers/easterEggEffects.ts';
import { createParticle, getResponsiveParticleCount, randomInRange, type ParticleConfig } from '@pages/about/controllers/easterEggParticles.ts';
import { setAnimationPhase } from '@pages/about/controllers/events.ts';
import type { AnimationHost, AnimationState, ColorPalette, OrbitRingConfig } from '@pages/about/controllers/types.ts';

export const initializeAmbientParticles = (state: AnimationState, host: AnimationHost | null): void => {
    const canvas = host?.getParticleCanvas();
    const scene = host?.getScene();
    if (!canvas) {
        return;
    }
    const particleCount = getResponsiveParticleCount(canvas, AMBIENT_PARTICLE_BASE);
    const palette = getPaletteByIndex(state.paletteIndex);
    const config: ParticleConfig = {
        count: particleCount,
        minSize: 4,
        maxSize: 10,
        colors: palette.particleColors
    };
    const centerX = canvas.clientWidth / 2;
    const centerY = canvas.clientHeight / 2;
    const particlesPerRing = Math.floor(particleCount / ORBIT_RINGS.length);
    for (let ringIndex = 0; ringIndex < ORBIT_RINGS.length; ringIndex++) {
        const orbitRing = resolveOrbitRingConfig(ringIndex);
        const isLastRing = ringIndex === ORBIT_RINGS.length - 1;
        const ringParticleCount = isLastRing ? particleCount - particlesPerRing * (ORBIT_RINGS.length - 1) : particlesPerRing;
        for (let particleIndex = 0; particleIndex < ringParticleCount; particleIndex++) {
            const particle = createParticle(config);
            particle.orbitRadius = randomInRange(orbitRing.minRadius, orbitRing.maxRadius);
            particle.orbitSpeed = randomInRange(orbitRing.minSpeed, orbitRing.maxSpeed);
            const angle = particle.orbitOffset;
            particle.x = centerX + Math.cos(angle) * particle.orbitRadius;
            particle.y = centerY + Math.sin(angle) * particle.orbitRadius;
            particle.targetX = particle.x;
            particle.targetY = particle.y;
            state.particles.push(particle);
        }
    }
    if (scene) {
        state.starfieldElement = createStarfield(scene, STARFIELD_COUNT);
    }
};

const resolveOrbitRingConfig = (ringIndex: number): OrbitRingConfig => {
    const ring = ORBIT_RINGS[ringIndex];
    if (!ring) {
        throw new Error(`Orbit ring config is missing for index ${String(ringIndex)}`);
    }
    return ring;
};

export const triggerColorRipple = (state: AnimationState, host: AnimationHost | null): void => {
    setAnimationPhase(state, host, 'exploding');
    state.paletteIndex = (state.paletteIndex + 1) % COLOR_PALETTES.length;
    applyPalette(host, getPaletteByIndex(state.paletteIndex));
    const canvas = host?.getParticleCanvas();
    if (!canvas) {
        return;
    }
    state.rippleStartTime = performance.now();
    state.particles.forEach((particle) => {
        particle.rippleDelay = scaleAnimationDurationMs(particle.orbitRadius * RIPPLE_WAVE_MS_PER_PX, canvas);
        particle.rippleRecolored = false;
    });
};

export const applyPalette = (host: AnimationHost | null, palette: ColorPalette): void => {
    const scene = host?.getScene();
    const orb = host?.getOrb();
    if (scene) {
        scene.style.setProperty('--ee-glow-color', palette.glowColor);
    }
    if (orb) {
        orb.style.setProperty('background', palette.orbGradient);
    }
};

/* SoAI - About page controllers events [frontend/assets/ts/pages/about/controllers/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { applyParticlePulsing, computeRippleEnvelope, getPaletteByIndex, pickPaletteParticleColor } from '@pages/about/controllers/animationHelpers.ts';
import { ATTRACTION_OUTER_RADIUS, ATTRACTION_STRENGTH, CELEBRATION_DURATION_MS, EXPLOSION_DURATION_MS, GLOW_MAX_DISTANCE, MAX_ORB_TILT, ORB_INTERACTION_RADIUS, REASSEMBLE_DURATION_MS, REPULSION_RADIUS, REPULSION_STRENGTH, RIPPLE_BLAST_SPEED_MAX, RIPPLE_BLAST_SPEED_MIN, RIPPLE_DECAY_MS, RIPPLE_LIFETIME_MS, RIPPLE_POP_SCALE, RIPPLE_RISE_MS } from '@pages/about/controllers/constants.ts';
import { calculateGlowIntensity } from '@pages/about/controllers/easterEggEffects.ts';
import { calculateRepulsion, randomInRange, type Particle } from '@pages/about/controllers/easterEggParticles.ts';
import type { ParticleCanvasRenderer } from '@pages/about/controllers/particleCanvasRendererController.ts';
import type { AnimationHost, AnimationState, ColorPalette } from '@pages/about/controllers/types.ts';

type AnimationPhase = AnimationState['phase'];

interface RippleWave {
    elapsed: number;
    riseMs: number;
    decayMs: number;
    palette: ColorPalette;
}

export const setAnimationPhase = (state: AnimationState, host: AnimationHost | null, phase: AnimationPhase): void => {
    state.phase = phase;
    state.phaseStartTime = performance.now();
    const orb = host?.getOrb();
    if (orb) {
        orb.setAttribute('data-phase', phase);
    }
};

export const tickAnimationFrame = (timestamp: number, state: AnimationState, host: AnimationHost | null, renderer: ParticleCanvasRenderer): void => {
    switch (state.phase) {
        case 'idle':
            updateOrbitingParticles(state, host, false);
            break;
        case 'hover':
            updateOrbitingParticles(state, host, true);
            updateOrbTilt(state, host);
            updateGlowProximity(state, host);
            break;
        case 'exploding':
            updateOrbitingParticles(state, host, false);
            advancePhaseWhenElapsed(timestamp, state, host, EXPLOSION_DURATION_MS, 'reassembling');
            break;
        case 'reassembling':
            updateOrbitingParticles(state, host, false);
            advancePhaseWhenElapsed(timestamp, state, host, REASSEMBLE_DURATION_MS, 'celebrating');
            break;
        case 'celebrating':
            updateOrbitingParticles(state, host, false);
            updateCelebratingOrb(timestamp, state, host);
            break;
    }
    renderer.render(state.particles);
};

const advancePhaseWhenElapsed = (timestamp: number, state: AnimationState, host: AnimationHost | null, baseDurationMs: number, nextPhase: AnimationPhase): void => {
    const elapsed = timestamp - state.phaseStartTime;
    const duration = scaleAnimationDurationMs(baseDurationMs, host?.getScene() ?? null);
    if (duration <= 0 || elapsed >= duration) {
        setAnimationPhase(state, host, nextPhase);
    }
};

const updateOrbitingParticles = (state: AnimationState, host: AnimationHost | null, applyCursorForces: boolean): void => {
    const canvas = host?.getParticleCanvas();
    if (!canvas) {
        return;
    }
    const centerX = canvas.clientWidth / 2;
    const centerY = canvas.clientHeight / 2;
    const time = performance.now() / 1000;
    const wave = resolveRippleWave(state, canvas);
    const cursor = applyCursorForces ? state.cursorPosition : null;
    const cursorActive = cursor !== null && performance.now() - state.lastMouseMoveTime < 3000;
    state.particles.forEach((particle) => {
        const rippleStrength = wave ? applyRippleWaveToParticle(particle, wave, centerX, centerY) : 0;
        const angle = particle.orbitOffset + time * particle.orbitSpeed;
        const radius = particle.orbitRadius + Math.sin(time * 1.5 + particle.orbitOffset) * 8;
        particle.targetX = centerX + Math.cos(angle) * radius;
        particle.targetY = centerY + Math.sin(angle) * radius;
        if (cursor && cursorActive) {
            applyCursorForcesToParticle(particle, cursor.x, cursor.y);
        } else {
            particle.vx *= 0.9;
            particle.vy *= 0.9;
        }
        particle.x += (particle.targetX - particle.x) * 0.04 + particle.vx;
        particle.y += (particle.targetY - particle.y) * 0.04 + particle.vy;
        applyParticlePulsing(particle, time);
        particle.scale += rippleStrength * RIPPLE_POP_SCALE;
        particle.opacity = clampNumber(particle.opacity + rippleStrength, 0, 1);
    });
};

const resolveRippleWave = (state: AnimationState, scope: HTMLElement): RippleWave | null => {
    const startTime = state.rippleStartTime;
    if (startTime === null) {
        return null;
    }
    const elapsed = performance.now() - startTime;
    if (elapsed >= scaleAnimationDurationMs(RIPPLE_LIFETIME_MS, scope)) {
        finalizeRippleWave(state);
        return null;
    }
    return {
        elapsed,
        riseMs: scaleAnimationDurationMs(RIPPLE_RISE_MS, scope),
        decayMs: scaleAnimationDurationMs(RIPPLE_DECAY_MS, scope),
        palette: getPaletteByIndex(state.paletteIndex)
    };
};

const finalizeRippleWave = (state: AnimationState): void => {
    const palette = getPaletteByIndex(state.paletteIndex);
    state.particles.forEach((particle) => {
        recolorParticleOnce(particle, palette);
    });
    state.rippleStartTime = null;
};

const applyRippleWaveToParticle = (particle: Particle, wave: RippleWave, centerX: number, centerY: number): number => {
    const localElapsed = wave.elapsed - particle.rippleDelay;
    if (localElapsed <= 0) {
        return 0;
    }
    if (!particle.rippleRecolored) {
        recolorParticleOnce(particle, wave.palette);
        applyRippleBlastImpulse(particle, centerX, centerY);
    }
    return computeRippleEnvelope(localElapsed, wave.riseMs, wave.decayMs);
};

const recolorParticleOnce = (particle: Particle, palette: ColorPalette): void => {
    if (particle.rippleRecolored) {
        return;
    }
    particle.color = pickPaletteParticleColor(palette);
    particle.rippleRecolored = true;
};

const applyRippleBlastImpulse = (particle: Particle, centerX: number, centerY: number): void => {
    const deltaX = particle.x - centerX;
    const deltaY = particle.y - centerY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const speed = randomInRange(RIPPLE_BLAST_SPEED_MIN, RIPPLE_BLAST_SPEED_MAX);
    if (distance < 0.1) {
        const angle = Math.random() * Math.PI * 2;
        particle.vx += Math.cos(angle) * speed;
        particle.vy += Math.sin(angle) * speed;
        return;
    }
    particle.vx += (deltaX / distance) * speed;
    particle.vy += (deltaY / distance) * speed;
};

const applyCursorForcesToParticle = (particle: Particle, cursorX: number, cursorY: number): void => {
    const dx = particle.x - cursorX;
    const dy = particle.y - cursorY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const particleJitter = 0.5 + (Math.sin(particle.orbitOffset * 7.3) + 1) * 0.5;
    const jitteredRadius = REPULSION_RADIUS * (0.6 + particleJitter * 0.8);
    const jitteredStrength = REPULSION_STRENGTH * (0.5 + particleJitter * 1);
    if (distance < jitteredRadius) {
        const repulsion = calculateRepulsion(particle, cursorX, cursorY, jitteredStrength, jitteredRadius);
        particle.vx = (particle.vx + repulsion.vx) * 0.8;
        particle.vy = (particle.vy + repulsion.vy) * 0.8;
    } else if (distance < ATTRACTION_OUTER_RADIUS) {
        const normalizedDistance = (distance - REPULSION_RADIUS) / (ATTRACTION_OUTER_RADIUS - REPULSION_RADIUS);
        const attractForce = (1 - normalizedDistance) * ATTRACTION_STRENGTH;
        const attractAngle = Math.atan2(-dy, -dx);
        particle.vx = (particle.vx + Math.cos(attractAngle) * attractForce) * 0.8;
        particle.vy = (particle.vy + Math.sin(attractAngle) * attractForce) * 0.8;
    } else {
        particle.vx *= 0.9;
        particle.vy *= 0.9;
    }
};

const updateGlowProximity = (state: AnimationState, host: AnimationHost | null): void => {
    const glowElement = host?.getGlowElement();
    const scene = host?.getScene();
    if (!glowElement || !scene) {
        return;
    }
    const cursor = state.cursorPosition;
    if (!cursor) {
        glowElement.style.setProperty('opacity', '0.6');
        return;
    }
    const centerX = scene.clientWidth / 2;
    const centerY = scene.clientHeight / 2;
    const intensity = calculateGlowIntensity(cursor.x, cursor.y, centerX, centerY, GLOW_MAX_DISTANCE);
    glowElement.style.setProperty('opacity', String(0.6 + intensity * 0.4));
};

const updateCelebratingOrb = (timestamp: number, state: AnimationState, host: AnimationHost | null): void => {
    const elapsed = timestamp - state.phaseStartTime;
    const duration = scaleAnimationDurationMs(CELEBRATION_DURATION_MS, host?.getScene() ?? null);
    const progress = duration <= 0 ? 1 : Math.min(elapsed / duration, 1);
    const orb = host?.getOrb();
    if (orb) {
        const targetScale = computeOrbHoverScale(state, host);
        const celebrateScale = progress < 0.5 ? 1 + 0.15 * Math.sin((progress / 0.5) * Math.PI) : 1.15 + (targetScale - 1.15) * (progress - 0.5) * (progress - 0.5) * (3 - 2 * (progress - 0.5));
        const glowSpread = progress < 0.5 ? 40 + 40 * Math.sin((progress / 0.5) * Math.PI) : 40;
        const glowOpacity = progress < 0.5 ? 40 + 30 * Math.sin((progress / 0.5) * Math.PI) : 40;
        orb.style.setProperty('transform', `scale(${String(celebrateScale)})`);
        orb.style.setProperty('box-shadow', `0 0 ${String(glowSpread)}px color-mix(in srgb, var(--ee-glow-color) ${String(glowOpacity)}%, transparent)`);
    }
    if (progress >= 1) {
        const nextPhase = state.cursorPosition ? 'hover' : 'idle';
        setAnimationPhase(state, host, nextPhase);
        host?.onCelebrationComplete();
    }
};

const updateOrbTilt = (state: AnimationState, host: AnimationHost | null): void => {
    const orb = host?.getOrb();
    const scene = host?.getScene();
    if (!orb || !scene) {
        return;
    }
    const cursor = state.cursorPosition;
    let orbScale = 1;
    if (!cursor) {
        state.orbRotation.x *= 0.9;
        state.orbRotation.y *= 0.9;
    } else {
        const sceneRect = measureLayoutBox(scene);
        const sceneCenterX = sceneRect.width / 2;
        const sceneCenterY = sceneRect.height / 2;
        const deltaX = cursor.x - sceneCenterX;
        const deltaY = cursor.y - sceneCenterY;
        const cursorDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        if (cursorDistance < ORB_INTERACTION_RADIUS) {
            const proximity = 1 - cursorDistance / ORB_INTERACTION_RADIUS;
            orbScale = 1 + proximity * 0.25;
        }
        const maxDistance = Math.min(sceneRect.width, sceneRect.height) / 2;
        const targetRotateY = clampNumber((deltaX / maxDistance) * MAX_ORB_TILT, -MAX_ORB_TILT, MAX_ORB_TILT);
        const targetRotateX = clampNumber((-deltaY / maxDistance) * MAX_ORB_TILT, -MAX_ORB_TILT, MAX_ORB_TILT);
        state.orbRotation.x += (targetRotateX - state.orbRotation.x) * 0.1;
        state.orbRotation.y += (targetRotateY - state.orbRotation.y) * 0.1;
    }
    orb.style.setProperty('transform', `rotateX(${String(state.orbRotation.x)}deg) rotateY(${String(state.orbRotation.y)}deg) scale(${String(orbScale)})`);
};

const computeOrbHoverScale = (state: AnimationState, host: AnimationHost | null): number => {
    const cursor = state.cursorPosition;
    if (!cursor) {
        return 1;
    }
    const scene = host?.getScene();
    if (!scene) {
        return 1;
    }
    const sceneRect = measureLayoutBox(scene);
    const deltaX = cursor.x - sceneRect.width / 2;
    const deltaY = cursor.y - sceneRect.height / 2;
    const cursorDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    if (cursorDistance >= ORB_INTERACTION_RADIUS) {
        return 1;
    }
    const proximity = 1 - cursorDistance / ORB_INTERACTION_RADIUS;
    return 1 + proximity * 0.25;
};

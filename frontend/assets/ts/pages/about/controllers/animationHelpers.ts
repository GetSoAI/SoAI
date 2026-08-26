/* SoAI - About page animation helpers [frontend/assets/ts/pages/about/controllers/animationHelpers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { COLOR_PALETTES } from '@pages/about/controllers/constants.ts';
import type { Particle } from '@pages/about/controllers/easterEggParticles.ts';
import type { ColorPalette } from '@pages/about/controllers/types.ts';

const getPaletteByIndex = (paletteIndex: number): ColorPalette => {
    const fallbackPalette = COLOR_PALETTES[0];
    const configuredPalette = COLOR_PALETTES[paletteIndex];
    if (configuredPalette) {
        return configuredPalette;
    }
    if (!fallbackPalette) {
        throw new Error('Easter egg color palette is not configured');
    }
    return fallbackPalette;
};

const pickPaletteParticleColor = (palette: ColorPalette): string => {
    const colors = palette.particleColors;
    const primaryColor = colors[0];
    if (!primaryColor) {
        throw new Error('Easter egg palette has no particle colors');
    }
    const index = Math.floor(Math.random() * colors.length);
    return colors[index] ?? primaryColor;
};

const computeRippleEnvelope = (elapsedSinceArrivalMs: number, riseMs: number, decayMs: number): number => {
    if (elapsedSinceArrivalMs <= 0 || riseMs <= 0 || decayMs <= 0) {
        return 0;
    }
    return (1 - Math.exp(-elapsedSinceArrivalMs / riseMs)) * Math.exp(-elapsedSinceArrivalMs / decayMs);
};

const applyParticlePulsing = (particle: Particle, time: number): void => {
    particle.opacity = 0.4 + 0.6 * ((Math.sin(time * particle.pulseSpeed + particle.orbitOffset) + 1) / 2);
    particle.scale = 0.85 + 0.15 * ((Math.sin(time * 0.8 + particle.orbitOffset * 2) + 1) / 2);
};

export { applyParticlePulsing, computeRippleEnvelope, getPaletteByIndex, pickPaletteParticleColor };

/* SoAI - About page controllers constants [frontend/assets/ts/pages/about/controllers/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ColorPalette, OrbitRingConfig } from '@pages/about/controllers/types.ts';

export const AMBIENT_PARTICLE_BASE = 520;
export const REPULSION_RADIUS = 110;
export const REPULSION_STRENGTH = 5;
export const ATTRACTION_OUTER_RADIUS = 200;
export const ATTRACTION_STRENGTH = 1.5;
export const MAX_ORB_TILT = 15;
export const EXPLOSION_DURATION_MS = 300;
export const REASSEMBLE_DURATION_MS = 500;
export const CELEBRATION_DURATION_MS = 600;
export const RIPPLE_WAVE_MS_PER_PX = 2.2;
export const RIPPLE_RISE_MS = 70;
export const RIPPLE_DECAY_MS = 320;
export const RIPPLE_LIFETIME_MS = 2000;
export const RIPPLE_BLAST_SPEED_MIN = 12;
export const RIPPLE_BLAST_SPEED_MAX = 22;
export const RIPPLE_POP_SCALE = 0.5;
export const STARFIELD_COUNT = 60;
export const GLOW_MAX_DISTANCE = 200;
export const ORB_INTERACTION_RADIUS = 60;

export const COLOR_PALETTES: readonly ColorPalette[] = [
    {
        particleColors: ['var(--accent-green)', '#4ade80', '#a3e635', '#facc15', '#fbbf24', '#d4d4d4'],
        glowColor: 'var(--accent-green)',
        orbGradient: 'linear-gradient(135deg, var(--accent-green) 0%, var(--accent-green-dark) 100%)'
    },
    {
        particleColors: ['#3b82f6', '#60a5fa', '#22d3ee', '#06b6d4', '#67e8f9', '#e0e7ff'],
        glowColor: '#3b82f6',
        orbGradient: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)'
    },
    {
        particleColors: ['#a855f7', '#c084fc', '#e879f9', '#f472b6', '#d946ef', '#e9d5ff'],
        glowColor: '#a855f7',
        orbGradient: 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)'
    }
];

export const ORBIT_RINGS: readonly OrbitRingConfig[] = [
    { minRadius: 35, maxRadius: 55, minSpeed: 0.8, maxSpeed: 1.5 },
    { minRadius: 65, maxRadius: 90, minSpeed: 0.4, maxSpeed: 0.9 },
    { minRadius: 100, maxRadius: 140, minSpeed: 0.15, maxSpeed: 0.45 }
];

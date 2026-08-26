/* SoAI - About page controllers state [frontend/assets/ts/pages/about/controllers/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AnimationState } from '@pages/about/controllers/types.ts';

export const createInitialAnimationState = (): AnimationState => ({
    phase: 'idle',
    particles: [],
    orbRotation: { x: 0, y: 0 },
    cursorPosition: null,
    animationFrame: null,
    phaseStartTime: 0,
    starfieldElement: null,
    lastMouseMoveTime: 0,
    paletteIndex: 0,
    rippleStartTime: null
});

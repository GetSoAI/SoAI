/* SoAI - Charts feature vertical scale glide [frontend/assets/ts/features/charts/scales/scaleGlide.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Scale } from '@features/charts/component/chartComponentTypes.ts';
import { easeOutCubic } from '@features/charts/viewport/easing.ts';

interface ScaleGlideState {
    active: boolean;
    startTime: number;
    fromMin: number;
    fromMax: number;
    toMin: number;
    toMax: number;
}

const SCALE_GLIDE_MS = 180;
const SCALE_TARGET_EPSILON_RATIO = 1e-9;

const createScaleGlideState = (): ScaleGlideState => ({ active: false, startTime: 0, fromMin: 0, fromMax: 0, toMin: 0, toMax: 0 });

const isSameTarget = (glide: ScaleGlideState, min: number, max: number): boolean => {
    const epsilon = Math.max(Math.abs(max - min), 1e-12) * SCALE_TARGET_EPSILON_RATIO;
    return Math.abs(glide.toMin - min) <= epsilon && Math.abs(glide.toMax - max) <= epsilon;
};

const stopScaleGlide = (glide: ScaleGlideState): void => {
    glide.active = false;
};

const glideScaleTowards = (glide: ScaleGlideState, scale: Scale, targetMin: number, targetMax: number, durationMs: number, now: number): void => {
    if (scale.min === null || scale.max === null || durationMs <= 0) {
        scale.min = glide.toMin = targetMin;
        scale.max = glide.toMax = targetMax;
        glide.active = false;
        return;
    }
    if (!glide.active || !isSameTarget(glide, targetMin, targetMax)) {
        if (!glide.active && scale.min === targetMin && scale.max === targetMax) return;
        Object.assign(glide, { active: true, startTime: now, fromMin: scale.min, fromMax: scale.max, toMin: targetMin, toMax: targetMax });
    }
    const progress = Math.max(0, (now - glide.startTime) / durationMs);
    if (progress >= 1) {
        scale.min = glide.toMin;
        scale.max = glide.toMax;
        glide.active = false;
        return;
    }
    const eased = easeOutCubic(progress);
    scale.min = glide.fromMin + (glide.toMin - glide.fromMin) * eased;
    scale.max = glide.fromMax + (glide.toMax - glide.fromMax) * eased;
};

export { createScaleGlideState, glideScaleTowards, SCALE_GLIDE_MS, stopScaleGlide };
export type { ScaleGlideState };

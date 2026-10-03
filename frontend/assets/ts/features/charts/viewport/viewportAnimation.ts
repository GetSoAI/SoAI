/* SoAI - Charts feature time viewport animation [frontend/assets/ts/features/charts/viewport/viewportAnimation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { easeOutCubic } from '@features/charts/viewport/easing.ts';
import type { TimeViewportState } from '@features/charts/viewport/timeViewport.ts';

interface ViewportAnimationState {
    active: boolean;
    startTime: number;
    durationMs: number;
    fromMsPerPx: number;
    toMsPerPx: number;
    fromAnchorTs: number;
    toAnchorTs: number;
    anchorOffsetPx: number;
}

interface ViewportAnimationTarget {
    msPerPx: number;
    anchorTs: number;
    anchorOffsetPx: number;
}

const createViewportAnimationState = (): ViewportAnimationState => ({ active: false, startTime: 0, durationMs: 0, fromMsPerPx: 0, toMsPerPx: 0, fromAnchorTs: 0, toAnchorTs: 0, anchorOffsetPx: 0 });

const applyAnimationFrame = (animation: ViewportAnimationState, time: TimeViewportState, progress: number): void => {
    const eased = easeOutCubic(progress);
    time.msPerPx = animation.fromMsPerPx * (animation.toMsPerPx / animation.fromMsPerPx) ** eased;
    time.rightEdgeTs = animation.fromAnchorTs + (animation.toAnchorTs - animation.fromAnchorTs) * eased + animation.anchorOffsetPx * time.msPerPx;
};

const startViewportAnimation = (animation: ViewportAnimationState, time: TimeViewportState, target: ViewportAnimationTarget, durationMs: number, now: number): void => {
    Object.assign(animation, {
        active: durationMs > 0,
        startTime: now,
        durationMs,
        fromMsPerPx: time.msPerPx,
        toMsPerPx: target.msPerPx,
        fromAnchorTs: time.rightEdgeTs - target.anchorOffsetPx * time.msPerPx,
        toAnchorTs: target.anchorTs,
        anchorOffsetPx: target.anchorOffsetPx
    });
    applyAnimationFrame(animation, time, durationMs > 0 ? 0 : 1);
};

const stepViewportAnimation = (animation: ViewportAnimationState, time: TimeViewportState, now: number): boolean => {
    if (!animation.active) return false;
    const progress = Math.min(1, Math.max(0, (now - animation.startTime) / animation.durationMs));
    applyAnimationFrame(animation, time, progress);
    animation.active = progress < 1;
    return animation.active;
};

const cancelViewportAnimation = (animation: ViewportAnimationState): void => {
    animation.active = false;
};

const shiftViewportAnimation = (animation: ViewportAnimationState, deltaTs: number): void => {
    animation.fromAnchorTs += deltaTs;
    animation.toAnchorTs += deltaTs;
};

export { cancelViewportAnimation, createViewportAnimationState, shiftViewportAnimation, startViewportAnimation, stepViewportAnimation };
export type { ViewportAnimationState, ViewportAnimationTarget };

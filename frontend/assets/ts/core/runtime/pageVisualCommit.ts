/* SoAI - Shared runtime page visual commit [frontend/assets/ts/core/runtime/pageVisualCommit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { requirePageTransitionSurface } from '@core/pageTransitions.ts';

interface PageVisualCommitHost {
    pageId: string;
    section: Element | null;
    flushDOMUpdates: () => void;
}

interface SurfaceLayoutSnapshot {
    width: number;
    height: number;
    top: number;
    left: number;
    childCount: number;
}

const STABLE_FRAME_COUNT = 8;

const awaitAnimationFrame = async (signal: AbortSignal | null): Promise<void> => {
    if (signalAborted(signal)) {
        return;
    }
    const requestAnimationFrame = getRequestAnimationFrame();
    await new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve());
    });
};

const readSurfaceLayout = (surface: Element): SurfaceLayoutSnapshot => {
    const rect = measureLayoutBox(surface);
    return {
        width: rect.width,
        height: rect.height,
        top: rect.top,
        left: rect.left,
        childCount: surface.childElementCount
    };
};

const isSameSurfaceLayout = (previous: SurfaceLayoutSnapshot, next: SurfaceLayoutSnapshot): boolean => {
    return previous.width === next.width && previous.height === next.height && previous.top === next.top && previous.left === next.left && previous.childCount === next.childCount;
};

const commitPageInitialVisualState = async (host: PageVisualCommitHost, signal: AbortSignal | null): Promise<void> => {
    host.flushDOMUpdates();
    await awaitAnimationFrame(signal);
    if (signalAborted(signal)) {
        return;
    }
    const section = host.section;
    if (!section) {
        throw new Error(`${host.pageId}: transition section missing before reveal`);
    }
    const { surface } = requirePageTransitionSurface(section);
    let stableFrames = 0;
    let previous = readSurfaceLayout(surface);
    while (stableFrames < STABLE_FRAME_COUNT) {
        await awaitAnimationFrame(signal);
        if (signalAborted(signal)) {
            return;
        }
        host.flushDOMUpdates();
        const next = readSurfaceLayout(surface);
        if (isSameSurfaceLayout(previous, next)) {
            stableFrames += 1;
        } else {
            stableFrames = 0;
            previous = next;
        }
    }
};

export { commitPageInitialVisualState };

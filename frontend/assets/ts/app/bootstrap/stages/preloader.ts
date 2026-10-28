/* SoAI - Frontend application preloader [frontend/assets/ts/app/bootstrap/stages/preloader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { restartVisibleWallpaperFadeIn, waitForActiveWallpaperReadiness } from '@core/backgroundtasks/wallpaperReadiness.ts';
import { announceDesktopLauncherBootReveal } from '@core/desktophost/desktopLauncher.ts';
import { getPerformance, requireDocument } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import { awaitPresentationFrame } from '@core/runtime/animationFrames.ts';
import { isArray } from '@core/typeGuards.ts';

const PRELOADER_EXITING_CLASS = 'page-preloader--exiting';

let preloaderFinalizationStarted = false;
let preloaderFinalizationPromise: Promise<void> | null = null;
let preloaderRevealReached = false;
const deferredBootStateReleases: Array<() => void> = [];

const markPreloaderRevealReached = (): void => {
    preloaderRevealReached = true;
    deferredBootStateReleases.splice(0).forEach((release) => release());
};

const releaseBootStateAfterPreloaderReveal = (release: () => void): void => {
    if (preloaderFinalizationStarted && !preloaderRevealReached) {
        deferredBootStateReleases.push(release);
        return;
    }
    release();
};

const resolvePreloader = (): HTMLElement | null => {
    const element = requireDocument().getElementById('page-preloader');
    return element instanceof HTMLElement ? element : null;
};

const establishVisiblePreloaderFrame = async (): Promise<void> => {
    await awaitPresentationFrame(null, 'Preloader exit was cancelled before its initial frame');
    await awaitPresentationFrame(null, 'Preloader exit was cancelled before its painted frame');
};

const removePreloader = (preloader: HTMLElement): void => {
    if (preloader.isConnected) {
        preloader.remove();
    }
};

const runPreloaderFinalization = async (preloader: HTMLElement): Promise<void> => {
    let readinessFailure: Error | null = null;
    try {
        await waitForActiveWallpaperReadiness();
    } catch (error) {
        readinessFailure = ensureError(error);
    }
    try {
        markPreloaderRevealReached();
        restartVisibleWallpaperFadeIn();
        await establishVisiblePreloaderFrame();
        if (!preloader.isConnected) {
            announceDesktopLauncherBootReveal();
            return;
        }
        preloader.classList.add(PRELOADER_EXITING_CLASS);
        preloader.setAttribute('aria-hidden', 'true');
        announceDesktopLauncherBootReveal();
        await waitForElementAnimations(preloader, { requireAnimation: true });
        if (readinessFailure) {
            throw readinessFailure;
        }
        removePreloader(preloader);
    } catch (error) {
        markPreloaderRevealReached();
        removePreloader(preloader);
        throw ensureError(error);
    }
};

const finalizePreloader = (): Promise<void> => {
    if (preloaderFinalizationStarted) {
        return preloaderFinalizationPromise ?? Promise.resolve();
    }
    preloaderFinalizationStarted = true;
    const preloader = resolvePreloader();
    if (!preloader) {
        preloaderFinalizationPromise = Promise.resolve();
        markPreloaderRevealReached();
        announceDesktopLauncherBootReveal();
        return preloaderFinalizationPromise;
    }
    preloaderFinalizationPromise = runPreloaderFinalization(preloader);
    return preloaderFinalizationPromise;
};

const detectNavigationReload = (): boolean => {
    const perf = getPerformance();
    const entries = perf.getEntriesByType('navigation');
    if (!isArray(entries) || entries.length === 0) {
        return false;
    }
    const first = entries[0];
    if (!(first instanceof PerformanceNavigationTiming)) {
        return false;
    }
    return first.type === 'reload';
};

export { detectNavigationReload, finalizePreloader, releaseBootStateAfterPreloaderReveal };

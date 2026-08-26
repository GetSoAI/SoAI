/* SoAI - Frontend application preloader [frontend/assets/ts/app/bootstrap/stages/preloader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { restartVisibleWallpaperFadeIn, waitForActiveWallpaperReadiness } from '@core/backgroundtasks/wallpaperReadiness.ts';
import { getComputedStyleStrict, getPerformance, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { isArray } from '@core/typeGuards.ts';

const PRELOADER_FADE_MS = 300;
const PRELOADER_EXITING_CLASS = 'page-preloader--exiting';
const PRELOADER_VISIBLE_CLASS = 'is-visible';
const PRELOADER_FREEZE_PROPERTIES: readonly string[] = Object.freeze(['visibility', 'position', 'top', 'right', 'bottom', 'left', 'display', 'align-items', 'justify-content', 'background', '-webkit-backdrop-filter', 'backdrop-filter', 'z-index']);
const PRELOADER_CONTENT_FREEZE_PROPERTIES: readonly string[] = Object.freeze(['display', 'flex-direction', 'align-items', 'justify-content', 'gap', 'text-align']);
const PRELOADER_LOGO_FREEZE_PROPERTIES: readonly string[] = Object.freeze(['display', 'width', 'max-width', 'height', 'aspect-ratio', 'object-fit', 'max-height', 'opacity', 'overflow', 'transform']);
const PRELOADER_SPINNER_FREEZE_PROPERTIES: readonly string[] = Object.freeze(['display', 'width', 'height', 'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width', 'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style', 'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color', 'border-radius', 'animation']);
const PRELOADER_TEXT_FREEZE_PROPERTIES: readonly string[] = Object.freeze(['display', 'max-width', 'color', 'font-size', 'font-weight', 'line-height']);

interface PreloaderFreezeTarget {
    selector: string;
    properties: readonly string[];
}

const PRELOADER_FREEZE_TARGETS: readonly PreloaderFreezeTarget[] = Object.freeze([
    { selector: '.page-preloader-content', properties: PRELOADER_CONTENT_FREEZE_PROPERTIES },
    { selector: '.page-preloader-logo', properties: PRELOADER_LOGO_FREEZE_PROPERTIES },
    { selector: '.page-preloader-spinner', properties: PRELOADER_SPINNER_FREEZE_PROPERTIES },
    { selector: '.page-preloader-text', properties: PRELOADER_TEXT_FREEZE_PROPERTIES }
]);

let preloaderFinalizationStarted = false;
let preloaderFinalizationPromise: Promise<void> | null = null;

const resolvePreloader = (): HTMLElement | null => {
    const element = requireDocument().getElementById('page-preloader');
    return element instanceof HTMLElement ? element : null;
};

const freezeElementStyles = (element: HTMLElement, properties: readonly string[]): void => {
    const computed = getComputedStyleStrict(element);
    for (const property of properties) {
        const value = computed.getPropertyValue(property);
        if (value) {
            element.style.setProperty(property, value);
        }
    }
};

const freezePreloaderLayout = (preloader: HTMLElement): void => {
    freezeElementStyles(preloader, PRELOADER_FREEZE_PROPERTIES);
    for (const target of PRELOADER_FREEZE_TARGETS) {
        const element = dom.resolve(target.selector, preloader);
        if (element instanceof HTMLElement) {
            freezeElementStyles(element, target.properties);
        }
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
        return preloaderFinalizationPromise;
    }
    preloaderFinalizationPromise = waitForActiveWallpaperReadiness()
        .then(() => {
            restartVisibleWallpaperFadeIn();
            freezePreloaderLayout(preloader);
            preloader.classList.remove(PRELOADER_VISIBLE_CLASS);
            preloader.classList.add(PRELOADER_EXITING_CLASS);
            preloader.setAttribute('aria-hidden', 'true');
            return sleepMs(PRELOADER_FADE_MS);
        })
        .then(() => {
            if (preloader.isConnected) {
                preloader.remove();
            }
        })
        .catch((error) => {
            errorHandler.warn('Preloader', 'Failed to remove preloader', ensureError(error));
        });
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

export { detectNavigationReload, finalizePreloader };

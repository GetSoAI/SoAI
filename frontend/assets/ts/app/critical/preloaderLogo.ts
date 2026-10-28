/* SoAI - Frontend application preloader logo [frontend/assets/ts/app/critical/preloaderLogo.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { resolveDesktopLauncherBootHandoff } from '@core/desktophost/desktopLauncher.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

const LOGO_PATHS = {
    dark: 'img/soai/soai-logo-dark.png',
    light: 'img/soai/soai-logo-light.png'
};

const REVEAL_DELAY_MS = 3000;
const STATUS_AFTER_LOGO_MS = 6000;
const LOGO_READY_CLASS = 'preloader-logo-ready';
const STATUS_READY_CLASS = 'preloader-status-ready';
const PRELOADER_LOGO_SELECTOR = '.page-preloader-logo';
const PRELOADER_CONTENT_SELECTOR = '.page-preloader-content';
const PRELOADER_STATUS_SELECTOR = '.page-preloader-status';
const PRELOADER_SPINNER_SELECTOR = '.page-preloader-spinner';
const MODULE_ID = 'critical.preloaderLogo';

type ThemeKey = keyof typeof LOGO_PATHS;

const getDocumentElement = (): HTMLElement => {
    const root = document.documentElement;
    if (!root) {
        throw new Error('Document element must exist for preloader logo');
    }
    return root;
};

const resolveTheme = (): ThemeKey => {
    const root = getDocumentElement();
    return root.classList.contains('theme-light') ? 'light' : 'dark';
};

const waitForDelay = async (duration: number): Promise<void> => {
    await sleepMs(duration);
};

const preloadLogo = (src: string): Promise<HTMLImageElement> => {
    const deferred = createDeferred<HTMLImageElement>();
    const image = new Image();
    image.decoding = 'async';
    image.onload = (): void => {
        if (typeof image.decode === 'function') {
            void image
                .decode()
                .then((): void => {
                    deferred.resolve(image);
                })
                .catch((error): void => {
                    deferred.reject(error);
                });
            return;
        }
        deferred.resolve(image);
    };
    image.onerror = (): void => {
        deferred.reject(new Error(`Failed to load preloader logo asset: ${src}`));
    };
    image.src = src;
    return deferred.promise;
};

const getLogoElement = (): HTMLImageElement | null => document.querySelector<HTMLImageElement>(PRELOADER_LOGO_SELECTOR);

const alignAnimationsToTimeline = (selectors: readonly string[], origin: number | null, subtree = false): void => {
    if (origin === null) {
        return;
    }
    const elapsed = Date.now() - origin;
    if (elapsed <= 0) {
        return;
    }
    for (const selector of selectors) {
        const element = dom.resolve(selector);
        if (!element || typeof element.getAnimations !== 'function') {
            continue;
        }
        for (const animation of element.getAnimations({ subtree })) {
            animation.currentTime = elapsed;
        }
    }
};

const applyLogo = (target: HTMLImageElement, source: HTMLImageElement, timelineOrigin: number | null): void => {
    const root = getDocumentElement();
    if (target.src !== source.src) {
        target.src = source.src;
    }
    target.decoding = 'async';
    if (root.classList.contains(LOGO_READY_CLASS)) {
        return;
    }
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            root.classList.add(LOGO_READY_CLASS);
            alignAnimationsToTimeline([PRELOADER_CONTENT_SELECTOR, PRELOADER_LOGO_SELECTOR], timelineOrigin);
        });
    });
};

const revealAmbientStage = (logoElement: HTMLImageElement, readyClass: string, timelineOrigin: number | null): boolean => {
    if (!logoElement.isConnected) {
        return false;
    }
    getDocumentElement().classList.add(readyClass);
    alignAnimationsToTimeline([PRELOADER_STATUS_SELECTOR], timelineOrigin);
    return true;
};

const initializePreloaderLogo = async (): Promise<void> => {
    const logoElement = getLogoElement();
    if (!logoElement) {
        return;
    }
    const theme = resolveTheme();
    const logoPath = resolveAssetPath(LOGO_PATHS[theme]);
    if (!logoPath) {
        throw new Error('Preloader logo path resolution failed');
    }
    const handoff = resolveDesktopLauncherBootHandoff();
    const logoAt = handoff ? handoff.startedAt + REVEAL_DELAY_MS : null;
    alignAnimationsToTimeline([PRELOADER_SPINNER_SELECTOR], handoff ? handoff.startedAt : null, true);

    const imagePromise = preloadLogo(logoPath);
    const [loadedImage] = await Promise.all([imagePromise, waitForDelay(logoAt === null ? REVEAL_DELAY_MS : Math.max(0, logoAt - Date.now()))]);
    if (!logoElement.isConnected) {
        return;
    }
    applyLogo(logoElement, loadedImage, logoAt);

    const statusAt = logoAt === null ? null : logoAt + STATUS_AFTER_LOGO_MS;
    await waitForDelay(statusAt === null ? STATUS_AFTER_LOGO_MS : Math.max(0, statusAt - Date.now()));
    revealAmbientStage(logoElement, STATUS_READY_CLASS, statusAt);
};

const startPreloaderLogo = (): void => {
    void initializePreloaderLogo().catch((error) => {
        errorHandler.error(MODULE_ID, 'Preloader logo initialization failed', error);
    });
};

export { initializePreloaderLogo, startPreloaderLogo };

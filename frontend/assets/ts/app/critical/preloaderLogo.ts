/* SoAI - Frontend application preloader logo [frontend/assets/ts/app/critical/preloaderLogo.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
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

const applyLogo = (target: HTMLImageElement, source: HTMLImageElement): void => {
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
        });
    });
};

const revealAmbientStage = (logoElement: HTMLImageElement, readyClass: string): boolean => {
    if (!logoElement.isConnected) {
        return false;
    }
    getDocumentElement().classList.add(readyClass);
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

    const imagePromise = preloadLogo(logoPath);
    const [loadedImage] = await Promise.all([imagePromise, waitForDelay(REVEAL_DELAY_MS)]);
    if (!logoElement.isConnected) {
        return;
    }
    applyLogo(logoElement, loadedImage);

    await waitForDelay(STATUS_AFTER_LOGO_MS);
    revealAmbientStage(logoElement, STATUS_READY_CLASS);
};

const startPreloaderLogo = (): void => {
    void initializePreloaderLogo().catch((error) => {
        errorHandler.error(MODULE_ID, 'Preloader logo initialization failed', error);
    });
};

export { initializePreloaderLogo, startPreloaderLogo };

/* SoAI - Shared background tasks wallpaper readiness [frontend/assets/ts/core/backgroundtasks/wallpaperReadiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { CONTENT_CHECK_DELAY_MS, WALLPAPER_BROWSER_CACHE_KEY } from '@core/backgroundtasks/constants.ts';
import { normalizeOverlayValue } from '@core/backgroundtasks/state.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import { removeStorageKey, readStorageJson, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface CachedWallpaperRecord {
    url: string;
    overlay: number;
    timestamp: number;
}

const EARLY_WALLPAPER_ATTRIBUTE = 'data-soai-early-wallpaper';
const EARLY_WALLPAPER_PENDING_ATTRIBUTE = 'data-soai-early-wallpaper-pending';
const EARLY_WALLPAPER_READY_ATTRIBUTE = 'data-soai-early-wallpaper-ready';
const WALLPAPER_READINESS_MODULE_ID = 'WallpaperReadiness';
const WALLPAPER_READINESS_TIMEOUT_MS = 5000;

let activeWallpaperUrl: string | null = null;
let activeWallpaperPromise: Promise<void> | null = null;

const normalizeCachedWallpaperUrl = (url: string): string | null => {
    try {
        const parsed = new URL(url.trim(), window.location.href);
        if ((parsed.protocol !== 'http:' && parsed.protocol !== 'https:') || parsed.origin !== window.location.origin) {
            return null;
        }
        return parsed.href;
    } catch (error) {
        errorHandler.warn(WALLPAPER_READINESS_MODULE_ID, 'Cached wallpaper URL normalization failed', ensureError(error));
        return null;
    }
};

const parseCachedWallpaperRecord = (value: JsonObject): CachedWallpaperRecord | null => {
    const url = value['url'];
    const overlay = value['overlay'];
    const timestamp = value['timestamp'];
    if (!isString(url) || !url.trim()) {
        return null;
    }
    const normalizedUrl = normalizeCachedWallpaperUrl(url);
    if (!normalizedUrl) {
        return null;
    }
    if (!isFiniteNumber(overlay) || !isFiniteNumber(timestamp)) {
        return null;
    }
    return {
        url: normalizedUrl,
        overlay: normalizeOverlayValue(overlay),
        timestamp
    };
};

const readCachedWallpaperRecord = (): CachedWallpaperRecord | null => {
    const value = readStorageJson('localStorage', WALLPAPER_BROWSER_CACHE_KEY);
    if (!isObject(value)) {
        return null;
    }
    return parseCachedWallpaperRecord(value);
};

const preloadWallpaperImage = (url: string): Promise<void> => {
    const image = new Image();
    image.decoding = 'async';
    return new Promise<void>((resolve, reject) => {
        image.onload = (): void => {
            if (typeof image.decode === 'function') {
                terminateHandledPromise(image.decode().then(resolve).catch(reject));
                return;
            }
            resolve();
        };
        image.onerror = (): void => {
            reject(new Error(`Failed to load wallpaper image: ${url}`));
        };
        image.src = url;
    });
};

const waitForAnimationFrame = async (): Promise<void> => {
    await new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve());
    });
};

const setRootEarlyWallpaperReady = (): void => {
    document.documentElement.removeAttribute(EARLY_WALLPAPER_PENDING_ATTRIBUTE);
    document.documentElement.setAttribute(EARLY_WALLPAPER_READY_ATTRIBUTE, 'true');
};

const clearRootEarlyWallpaperState = (): void => {
    document.documentElement.removeAttribute(EARLY_WALLPAPER_ATTRIBUTE);
    document.documentElement.removeAttribute(EARLY_WALLPAPER_PENDING_ATTRIBUTE);
    document.documentElement.removeAttribute(EARLY_WALLPAPER_READY_ATTRIBUTE);
};

const setActiveWallpaperReadiness = (url: string): Promise<void> => {
    const normalizedUrl = url.trim();
    if (!normalizedUrl) {
        throw new Error('Wallpaper readiness requires a non-empty URL');
    }
    if (activeWallpaperUrl === normalizedUrl && activeWallpaperPromise) {
        return activeWallpaperPromise;
    }
    activeWallpaperUrl = normalizedUrl;
    activeWallpaperPromise = preloadWallpaperImage(normalizedUrl).catch((error) => {
        throw ensureError(error);
    });
    void activeWallpaperPromise.catch((error) => {
        errorHandler.warn(WALLPAPER_READINESS_MODULE_ID, 'Active wallpaper preload failed', ensureError(error));
    });
    return activeWallpaperPromise;
};

const clearActiveWallpaperReadiness = (): void => {
    activeWallpaperUrl = null;
    activeWallpaperPromise = null;
};

const restartVisibleWallpaperFadeIn = (): void => {
    const body = document.body;
    if (!(body instanceof HTMLBodyElement) || !body.classList.contains('has-wallpaper')) {
        return;
    }
    body.classList.remove('has-wallpaper');
    body.classList.remove('wallpaper-ready');
    void body.offsetWidth;
    body.classList.add('has-wallpaper');
    window.setTimeout(
        () => {
            body.classList.add('wallpaper-ready');
        },
        scaleAnimationDurationMs(600, body)
    );
};

const clearWallpaperCache = (): void => {
    removeStorageKey('localStorage', WALLPAPER_BROWSER_CACHE_KEY);
    clearActiveWallpaperReadiness();
};

const waitForActiveWallpaperReadiness = async (): Promise<void> => {
    if (!activeWallpaperPromise) {
        return;
    }
    try {
        await withTimeout(activeWallpaperPromise, {
            timeoutMs: WALLPAPER_READINESS_TIMEOUT_MS,
            timeoutMessage: 'Wallpaper readiness timed out'
        });
        await sleepMs(CONTENT_CHECK_DELAY_MS);
        await waitForAnimationFrame();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn(WALLPAPER_READINESS_MODULE_ID, 'Wallpaper readiness failed before preloader finalization', runtimeError);
        clearWallpaperCache();
        clearRootEarlyWallpaperState();
    }
};

const writeWallpaperCache = (url: string, overlay: number): void => {
    const normalizedUrl = url.trim();
    if (!normalizedUrl) {
        throw new Error('Wallpaper cache requires a non-empty URL');
    }
    const value: JsonValue = {
        url: normalizedUrl,
        overlay: normalizeOverlayValue(overlay),
        timestamp: Date.now()
    };
    writeStorageJson('localStorage', WALLPAPER_BROWSER_CACHE_KEY, value);
};

const startCachedWallpaperReadiness = (): void => {
    let cached: CachedWallpaperRecord | null = null;
    try {
        cached = readCachedWallpaperRecord();
    } catch (error) {
        errorHandler.warn(WALLPAPER_READINESS_MODULE_ID, 'Failed to read cached wallpaper', ensureError(error));
        clearWallpaperCache();
        clearRootEarlyWallpaperState();
        return;
    }
    if (!cached) {
        clearRootEarlyWallpaperState();
        return;
    }
    void setActiveWallpaperReadiness(cached.url)
        .then(() => {
            setRootEarlyWallpaperReady();
        })
        .catch((error) => {
            errorHandler.warn(WALLPAPER_READINESS_MODULE_ID, 'Cached wallpaper failed to load', ensureError(error));
            clearWallpaperCache();
            clearRootEarlyWallpaperState();
        });
};

export { clearActiveWallpaperReadiness, clearWallpaperCache, restartVisibleWallpaperFadeIn, setActiveWallpaperReadiness, startCachedWallpaperReadiness, waitForActiveWallpaperReadiness, writeWallpaperCache };

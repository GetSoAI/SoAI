/* SoAI - Shared background tasks actions [frontend/assets/ts/core/backgroundtasks/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { onNavigationComplete, type NavigationEventHandler } from '@core/navigationEvents.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { isBoolean, isObject, isString } from '@core/typeGuards.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { CONTENT_CHECK_DELAY_MS, CONTENT_CHECK_INITIAL_DELAY_MS, MAX_CONTENT_ATTEMPTS } from '@core/backgroundtasks/constants.ts';
import { resolveAuthManager, resolveStorage } from '@core/backgroundtasks/adapters.ts';
import { applySolidBackgroundCSS, applyWallpaperCSS, applyWallpaperOverlay, clearBackgroundClasses, getMainContainer, removeWallpaperStyles, requireBody } from '@core/backgroundtasks/effects.ts';
import { hasLoadableContent, isValidCssColor, normalizeOverlayValue, normalizeRoute } from '@core/backgroundtasks/state.ts';
import { clearActiveWallpaperReadiness, clearWallpaperCache, setActiveWallpaperReadiness, writeWallpaperCache } from '@core/backgroundtasks/wallpaperReadiness.ts';
import type { BackgroundTasksInitializationOptions, BackgroundTasksRuntime } from '@core/backgroundtasks/internalContracts.ts';
import type { BackgroundRoute } from '@core/backgroundtasks/types.ts';
const clearWallpaperTimers = (service: BackgroundTasksRuntime): void => {
    if (service.wallpaperContentCheckTimerId !== null) {
        clearTimeout(service.wallpaperContentCheckTimerId);
        service.wallpaperContentCheckTimerId = null;
    }
    if (service.wallpaperAnimationTimerId !== null) {
        clearTimeout(service.wallpaperAnimationTimerId);
        service.wallpaperAnimationTimerId = null;
    }
};
const clearSolidBgTimers = (service: BackgroundTasksRuntime): void => {
    if (service.solidBgContentCheckTimerId !== null) {
        clearTimeout(service.solidBgContentCheckTimerId);
        service.solidBgContentCheckTimerId = null;
    }
    if (service.solidBgAnimationTimerId !== null) {
        clearTimeout(service.solidBgAnimationTimerId);
        service.solidBgAnimationTimerId = null;
    }
};
const clearAllTimers = (service: BackgroundTasksRuntime): void => {
    clearWallpaperTimers(service);
    clearSolidBgTimers(service);
};
const createNavigationHandler = (service: BackgroundTasksRuntime): NavigationEventHandler => {
    const router = requireRouter();
    return (detail): void => {
        const route = detail?.['route'] ?? router.getCurrentRoute();
        applyBackgroundRoute(service, route);
    };
};
const initializeBackgroundTasks = async (service: BackgroundTasksRuntime, { force = false, signal }: BackgroundTasksInitializationOptions = {}): Promise<void> => {
    if (service.initialized && !force) {
        return;
    }
    if (force) {
        service.initialized = false;
        service.animationShown = false;
    }
    await detectWallpaper(service, signal);
    if (signal?.aborted) {
        return;
    }
    service.initialized = true;
    if (!service.navigationUnsubscribe) {
        service.navigationUnsubscribe = onNavigationComplete(createNavigationHandler(service));
    }
};
const detectWallpaper = async (service: BackgroundTasksRuntime, signal?: AbortSignal): Promise<void> => {
    const auth = resolveAuthManager();
    if (!auth.isAuthenticated) {
        disableBackground(service);
        return;
    }
    let snapshot;
    try {
        snapshot = await getWebSocketClient().requestSnapshot('webui.wallpaper.status', null, { signal, timeoutMs: 3500 });
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) {
            throw runtimeError;
        }
        errorHandler.debug('BackgroundTasks', 'Wallpaper status snapshot unavailable', runtimeError);
        disableBackground(service);
        return;
    }
    const response = snapshot?.data;
    if (!response || !isObject(response)) {
        disableBackground(service);
        return;
    }
    if (!isBoolean(response['exists'])) {
        disableBackground(service);
        return;
    }
    if (response['exists']) {
        const url = response['url'];
        if (!isString(url) || !url.trim()) {
            throw new Error('Wallpaper status must include url');
        }
        service.wallpaperUrl = url.trim();
        service.wallpaperAvailable = true;
        service.solidBackgroundColor = null;
        service.solidBackgroundAvailable = false;
        terminateHandledPromise(setActiveWallpaperReadiness(service.wallpaperUrl));
        clearAllTimers(service);
        return;
    }
    clearWallpaperCache();
    const storage = resolveStorage();
    const solidColor = storage.getSolidBackground();
    if (isString(solidColor) && solidColor.trim()) {
        service.solidBackgroundColor = solidColor.trim();
        service.solidBackgroundAvailable = true;
        service.wallpaperUrl = null;
        service.wallpaperAvailable = false;
        clearAllTimers(service);
        return;
    }
    disableBackground(service);
};
const refreshBackgroundTasks = async (service: BackgroundTasksRuntime): Promise<void> => {
    service.animationShown = false;
    await detectWallpaper(service);
    const router = requireRouter();
    applyBackgroundRoute(service, router.getCurrentRoute());
};
const applyBackgroundRoute = (service: BackgroundTasksRuntime, route: BackgroundRoute | undefined): void => {
    clearAllTimers(service);
    const body = requireBody();
    const normalized = normalizeRoute(route);
    updateBodyRouteClass(body, normalized);
    if (!service.wallpaperAvailable && !service.solidBackgroundAvailable) {
        disableBackground(service);
        return;
    }
    if (service.excludedRoutes.has(normalized)) {
        clearBackgroundClasses(body);
        return;
    }
    if (service.wallpaperAvailable) {
        waitForContentAndApplyWallpaper(service);
    } else if (service.solidBackgroundAvailable) {
        waitForContentAndApplySolidBackground(service);
    }
};
const hasContent = (): boolean => {
    const container = getMainContainer();
    return hasLoadableContent(container);
};
const waitForContentAndApplyWallpaper = (service: BackgroundTasksRuntime): void => {
    clearWallpaperTimers(service);
    const applyWallpaper = (): void => {
        service.wallpaperContentCheckTimerId = null;
        applyWallpaperStyles(service);
        const body = requireBody();
        if (!service.animationShown) {
            service.animationShown = true;
            clearBackgroundClasses(body);
            dom.removeClass(body, 'has-solid-background');
            dom.removeClass(body, 'solid-background-ready');
            dom.addClass(body, 'has-wallpaper');
            service.wallpaperAnimationTimerId = setTimeout(
                () => {
                    service.wallpaperAnimationTimerId = null;
                    dom.addClass(body, 'wallpaper-ready');
                },
                scaleAnimationDurationMs(300, body)
            );
        } else {
            dom.removeClass(body, 'has-solid-background');
            dom.removeClass(body, 'solid-background-ready');
            dom.addClass(body, 'has-wallpaper');
            dom.addClass(body, 'wallpaper-ready');
        }
    };
    if (hasContent()) {
        service.wallpaperContentCheckTimerId = setTimeout(applyWallpaper, CONTENT_CHECK_DELAY_MS);
        return;
    }
    let attempts = 0;
    const checkContent = (): void => {
        attempts++;
        if (hasContent() || attempts >= MAX_CONTENT_ATTEMPTS) {
            applyWallpaper();
            return;
        }
        service.wallpaperContentCheckTimerId = setTimeout(checkContent, CONTENT_CHECK_DELAY_MS);
    };
    service.wallpaperContentCheckTimerId = setTimeout(checkContent, CONTENT_CHECK_INITIAL_DELAY_MS);
};
const waitForContentAndApplySolidBackground = (service: BackgroundTasksRuntime): void => {
    clearSolidBgTimers(service);
    const applySolidBackground = (): void => {
        service.solidBgContentCheckTimerId = null;
        applySolidBackgroundStyles(service);
        const body = requireBody();
        if (!service.animationShown) {
            service.animationShown = true;
            clearBackgroundClasses(body);
            dom.removeClass(body, 'has-wallpaper');
            dom.removeClass(body, 'wallpaper-ready');
            dom.addClass(body, 'has-solid-background');
            service.solidBgAnimationTimerId = setTimeout(
                () => {
                    service.solidBgAnimationTimerId = null;
                    dom.addClass(body, 'solid-background-ready');
                },
                scaleAnimationDurationMs(300, body)
            );
        } else {
            dom.removeClass(body, 'has-wallpaper');
            dom.removeClass(body, 'wallpaper-ready');
            dom.addClass(body, 'has-solid-background');
            dom.addClass(body, 'solid-background-ready');
        }
    };
    if (hasContent()) {
        service.solidBgContentCheckTimerId = setTimeout(applySolidBackground, CONTENT_CHECK_DELAY_MS);
        return;
    }
    let attempts = 0;
    const checkContent = (): void => {
        attempts++;
        if (hasContent() || attempts >= MAX_CONTENT_ATTEMPTS) {
            applySolidBackground();
            return;
        }
        service.solidBgContentCheckTimerId = setTimeout(checkContent, CONTENT_CHECK_DELAY_MS);
    };
    service.solidBgContentCheckTimerId = setTimeout(checkContent, CONTENT_CHECK_INITIAL_DELAY_MS);
};
const applyWallpaperStyles = (service: BackgroundTasksRuntime): void => {
    if (!isString(service.wallpaperUrl) || !service.wallpaperUrl.trim()) {
        throw new Error('Wallpaper URL is not set');
    }
    const url = service.wallpaperUrl.trim();
    applyWallpaperCSS(url);
    const storage = resolveStorage();
    const overlay = normalizeOverlayValue(storage.getWallpaperOverlay());
    applyWallpaperOverlay(overlay);
    writeWallpaperCache(url, overlay);
    terminateHandledPromise(setActiveWallpaperReadiness(url));
};
const applyWallpaperOverlayStyle = (service: BackgroundTasksRuntime): void => {
    const storage = resolveStorage();
    const overlay = normalizeOverlayValue(storage.getWallpaperOverlay());
    applyWallpaperOverlay(overlay);
    if (isString(service.wallpaperUrl) && service.wallpaperUrl.trim()) {
        writeWallpaperCache(service.wallpaperUrl.trim(), overlay);
    }
};
const applySolidBackgroundStyles = (service: BackgroundTasksRuntime): void => {
    if (!isString(service.solidBackgroundColor) || !service.solidBackgroundColor.trim()) {
        return;
    }
    const color = service.solidBackgroundColor.trim();
    if (!isValidCssColor(color)) {
        return;
    }
    applySolidBackgroundCSS(color);
};
const disableBackground = (service: BackgroundTasksRuntime): void => {
    clearAllTimers(service);
    clearActiveWallpaperReadiness();
    service.wallpaperAvailable = false;
    service.wallpaperUrl = null;
    service.solidBackgroundAvailable = false;
    service.solidBackgroundColor = null;
    const body = requireBody();
    clearBackgroundClasses(body);
    removeWallpaperStyles();
};
const updateBodyRouteClass = (body: HTMLElement, route: string): void => {
    const toRemove: string[] = [];
    const classes = dom.getClasses(body);
    classes.forEach((cls: string) => {
        if (cls.startsWith('page-')) {
            toRemove.push(cls);
        }
    });
    toRemove.forEach((cls) => dom.removeClass(body, cls));
    if (route) {
        dom.addClass(body, `${'page-'}${route}`);
    }
};
const disableWallpaper = (service: BackgroundTasksRuntime): void => {
    disableBackground(service);
};
export { applyBackgroundRoute, applySolidBackgroundStyles, applyWallpaperOverlayStyle, applyWallpaperStyles, clearAllTimers, disableBackground, disableWallpaper, detectWallpaper, initializeBackgroundTasks, refreshBackgroundTasks, waitForContentAndApplySolidBackground, waitForContentAndApplyWallpaper };

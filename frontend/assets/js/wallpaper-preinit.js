/* SoAI - Critical frontend wallpaper preinitialization [frontend/assets/js/wallpaper-preinit.js] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

'use strict';
(() => {
    const WALLPAPER_STORAGE_KEY = 'soai.ui.wallpaper.cache';
    const EARLY_WALLPAPER_ATTRIBUTE = 'data-soai-early-wallpaper';
    const EARLY_WALLPAPER_PENDING_ATTRIBUTE = 'data-soai-early-wallpaper-pending';
    const getGlobalScope = () => (typeof window !== 'undefined' ? window : null);
    const preinitIssueReporter = {
        report: (reason) => {
            const root = getGlobalScope()?.document?.documentElement;
            if (!(root instanceof HTMLElement)) {
                return;
            }
            if (!root.dataset['soaiWallpaperPreinitIssue']) {
                root.dataset['soaiWallpaperPreinitIssue'] = reason;
            }
        }
    };
    const safeGetLocalStorage = (scope) => {
        try {
            return scope.localStorage || null;
        } catch {
            preinitIssueReporter.report('localStorage-access-failed');
            return null;
        }
    };
    const isWallpaperCacheValue = (value) => {
        if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
        if (typeof value === 'number') return Number.isFinite(value);
        if (Array.isArray(value)) return value.every(isWallpaperCacheValue);
        if (typeof value !== 'object') return false;
        return Object.values(value).every(isWallpaperCacheValue);
    };
    const isWallpaperCacheObject = (value) => typeof value === 'object' && value !== null && !Array.isArray(value);
    const parseWallpaperCacheValue = (value) => {
        const parsed = JSON.parse(value);
        if (!isWallpaperCacheValue(parsed)) {
            throw new TypeError('Wallpaper cache must contain finite JSON data');
        }
        return parsed;
    };
    const clearWallpaperCache = (storage) => {
        try {
            storage.removeItem(WALLPAPER_STORAGE_KEY);
        } catch {
            preinitIssueReporter.report('wallpaper-cache-remove-failed');
        }
    };
    const normalizeWallpaperOverlay = (value) => {
        if (typeof value !== 'number' || !Number.isFinite(value)) {
            return 0;
        }
        return Math.min(100, Math.max(0, Math.round(value)));
    };
    const normalizeWallpaperUrl = (scope, value) => {
        if (typeof value !== 'string') {
            return null;
        }
        const trimmed = value.trim();
        if (!trimmed.length) {
            return null;
        }
        try {
            const parsed = new globalThis.URL(trimmed, scope.location.href);
            if ((parsed.protocol !== 'http:' && parsed.protocol !== 'https:') || parsed.origin !== scope.location.origin) {
                return null;
            }
            return parsed.href;
        } catch {
            preinitIssueReporter.report('wallpaper-url-invalid');
            return null;
        }
    };
    const readWallpaperCache = (scope) => {
        const storage = safeGetLocalStorage(scope);
        if (!storage) {
            return null;
        }
        let stored = null;
        try {
            stored = storage.getItem(WALLPAPER_STORAGE_KEY);
        } catch {
            preinitIssueReporter.report('wallpaper-cache-read-failed');
            return null;
        }
        if (!stored) return null;
        let parsed;
        try {
            parsed = parseWallpaperCacheValue(stored);
        } catch {
            preinitIssueReporter.report('wallpaper-cache-parse-failed');
            clearWallpaperCache(storage);
            return null;
        }
        if (!isWallpaperCacheObject(parsed)) {
            clearWallpaperCache(storage);
            return null;
        }
        const url = normalizeWallpaperUrl(scope, parsed['url']);
        if (!url || typeof parsed['timestamp'] !== 'number' || !Number.isFinite(parsed['timestamp'])) {
            clearWallpaperCache(storage);
            return null;
        }
        return { url, overlay: normalizeWallpaperOverlay(parsed['overlay']) };
    };
    const appendWallpaperPreloadLink = (scope, url) => {
        const head = scope.document.head;
        if (!(head instanceof HTMLHeadElement)) {
            return;
        }
        const link = scope.document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = url;
        head.appendChild(link);
    };
    const applyWallpaperPreinit = (root) => {
        root.setAttribute(EARLY_WALLPAPER_ATTRIBUTE, 'true');
        root.setAttribute(EARLY_WALLPAPER_PENDING_ATTRIBUTE, 'true');
    };
    const initializeWallpaperPreinit = () => {
        const scope = getGlobalScope();
        const root = scope?.document?.documentElement;
        if (!scope || !(root instanceof HTMLElement)) {
            return;
        }
        const wallpaper = readWallpaperCache(scope);
        if (wallpaper) {
            appendWallpaperPreloadLink(scope, wallpaper.url);
            applyWallpaperPreinit(root);
        }
    };
    try {
        initializeWallpaperPreinit();
    } catch {
        preinitIssueReporter.report('initialization-failed');
    }
})();

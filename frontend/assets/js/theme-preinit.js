/* SoAI - Critical frontend theme preinitialization [frontend/assets/js/theme-preinit.js] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

'use strict';
(() => {
    const THEME_STORAGE_KEY = 'soai.ui.theme';
    const ANIMATION_SPEED_STORAGE_KEY = 'soai.ui.animation_speed';
    const ANIMATION_SPEED_ATTRIBUTE = 'data-animation-speed';
    const INTERFACE_SCALE_STORAGE_KEY = 'soai.ui.interface_scale';
    const INTERFACE_SCALE_ATTRIBUTE = 'data-interface-scale';
    const DEFAULT_THEME = 'dark';
    const DEFAULT_ANIMATION_SPEED = 'normal';
    const DEFAULT_INTERFACE_SCALE_PERCENT = 100;
    const INTERFACE_SCALE_PERCENT_STEPS = [50, 75, 100, 125, 150];
    const isThemePreference = (value) => {
        if (value === 'light' || value === 'dark' || value === 'auto') {
            return true;
        }
        return false;
    };
    const isAnimationSpeed = (value) => {
        if (value === 'normal' || value === 'fast') {
            return true;
        }
        return false;
    };
    const isInterfaceScalePercent = (value) => INTERFACE_SCALE_PERCENT_STEPS.some((step) => step === value);
    const getGlobalScope = () => (typeof window !== 'undefined' ? window : null);
    const preinitIssueReporter = {
        report: (reason) => {
            const root = getGlobalScope()?.document?.documentElement;
            if (!(root instanceof HTMLElement)) {
                return;
            }
            if (!root.dataset['soaiThemePreinitIssue']) {
                root.dataset['soaiThemePreinitIssue'] = reason;
            }
        }
    };
    const safeGetLocalStorage = (scope) => {
        try {
            const storage = scope.localStorage;
            if (!storage) {
                return null;
            }
            return storage;
        } catch {
            preinitIssueReporter.report('localStorage-access-failed');
            return null;
        }
    };
    const normalizeStoredScalar = (value) => {
        if (typeof value !== 'string') {
            return null;
        }
        const trimmed = value.trim();
        if (!trimmed.length) {
            return null;
        }
        const normalizedValue = trimmed.startsWith('"') && trimmed.endsWith('"') ? trimmed.slice(1, -1).trim() : trimmed;
        if (!normalizedValue.length) {
            return null;
        }
        return normalizedValue.length ? normalizedValue : null;
    };
    const normalizeStoredPreference = (value) => {
        const normalizedValue = normalizeStoredScalar(value);
        if (!normalizedValue) {
            return null;
        }
        const lowered = normalizedValue.toLowerCase();
        if (isThemePreference(lowered)) {
            return lowered;
        }
        return null;
    };
    const normalizeStoredAnimationSpeed = (value) => {
        const normalizedValue = normalizeStoredScalar(value);
        if (!normalizedValue) {
            return null;
        }
        const lowered = normalizedValue.toLowerCase();
        if (isAnimationSpeed(lowered)) {
            return lowered;
        }
        return null;
    };
    const normalizeStoredInterfaceScale = (value) => {
        const normalizedValue = normalizeStoredScalar(value);
        if (!normalizedValue) {
            return null;
        }
        const numericValue = Number(normalizedValue);
        return isInterfaceScalePercent(numericValue) ? numericValue : null;
    };
    const readThemePreference = (scope) => {
        if (!scope) {
            preinitIssueReporter.report('no-window-scope');
            return DEFAULT_THEME;
        }
        const storage = safeGetLocalStorage(scope);
        if (!storage) {
            preinitIssueReporter.report('storage-unavailable');
            return DEFAULT_THEME;
        }
        try {
            const stored = storage.getItem(THEME_STORAGE_KEY);
            const normalized = normalizeStoredPreference(stored);
            if (normalized) {
                return normalized;
            }
        } catch {
            preinitIssueReporter.report('storage-read-failed');
            return DEFAULT_THEME;
        }
        return DEFAULT_THEME;
    };
    const readAnimationSpeed = (scope) => {
        if (!scope) {
            return DEFAULT_ANIMATION_SPEED;
        }
        const storage = safeGetLocalStorage(scope);
        if (!storage) {
            return DEFAULT_ANIMATION_SPEED;
        }
        try {
            const stored = storage.getItem(ANIMATION_SPEED_STORAGE_KEY);
            const normalized = normalizeStoredAnimationSpeed(stored);
            if (normalized) {
                return normalized;
            }
        } catch {
            preinitIssueReporter.report('animation-speed-storage-read-failed');
            return DEFAULT_ANIMATION_SPEED;
        }
        return DEFAULT_ANIMATION_SPEED;
    };
    const readInterfaceScale = (scope) => {
        if (!scope) {
            return DEFAULT_INTERFACE_SCALE_PERCENT;
        }
        const storage = safeGetLocalStorage(scope);
        if (!storage) {
            return DEFAULT_INTERFACE_SCALE_PERCENT;
        }
        try {
            return normalizeStoredInterfaceScale(storage.getItem(INTERFACE_SCALE_STORAGE_KEY)) ?? DEFAULT_INTERFACE_SCALE_PERCENT;
        } catch {
            preinitIssueReporter.report('interface-scale-storage-read-failed');
            return DEFAULT_INTERFACE_SCALE_PERCENT;
        }
    };
    const resolveTheme = (scope, preference) => {
        if (preference === 'light' || preference === 'dark') {
            return preference;
        }
        if (scope && typeof scope.matchMedia === 'function') {
            const query = '(prefers-color-scheme: dark)';
            const isDark = scope.matchMedia(query).matches;
            return isDark ? 'dark' : 'light';
        }
        return DEFAULT_THEME;
    };
    const applyTheme = (root, preference, actualTheme) => {
        root.classList.remove('theme-dark', 'theme-light');
        root.classList.add(`theme-${actualTheme}`);
        root.dataset['soaiThemePreference'] = preference;
        root.style.setProperty('color-scheme', actualTheme);
    };
    const applyAnimationSpeed = (root, speed) => {
        root.setAttribute(ANIMATION_SPEED_ATTRIBUTE, speed);
    };
    const applyInterfaceScale = (root, percent) => {
        root.setAttribute(INTERFACE_SCALE_ATTRIBUTE, String(percent));
    };
    const initializeTheme = () => {
        const scope = getGlobalScope();
        const preference = readThemePreference(scope);
        const animationSpeed = readAnimationSpeed(scope);
        const interfaceScale = readInterfaceScale(scope);
        const actualTheme = resolveTheme(scope, preference);
        const documentElement = scope?.document?.documentElement;
        if (documentElement && documentElement instanceof HTMLElement) {
            applyTheme(documentElement, preference, actualTheme);
            applyAnimationSpeed(documentElement, animationSpeed);
            applyInterfaceScale(documentElement, interfaceScale);
        }
    };
    try {
        initializeTheme();
    } catch {
        preinitIssueReporter.report('initialization-failed');
    }
})();

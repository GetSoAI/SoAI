/* SoAI - Critical frontend theme preinit [frontend/assets/ts/critical/themePreinit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

((): void => {
    type ThemePreference = 'light' | 'dark' | 'auto';
    type ResolvedTheme = 'light' | 'dark';
    type AnimationSpeed = 'normal' | 'fast';
    type InterfaceScalePercent = 50 | 75 | 100 | 125 | 150;

    const THEME_STORAGE_KEY = 'soai.ui.theme';
    const ANIMATION_SPEED_STORAGE_KEY = 'soai.ui.animation_speed';
    const ANIMATION_SPEED_ATTRIBUTE = 'data-animation-speed';
    const INTERFACE_SCALE_STORAGE_KEY = 'soai.ui.interface_scale';
    const INTERFACE_SCALE_ATTRIBUTE = 'data-interface-scale';
    const DEFAULT_THEME: ResolvedTheme = 'dark';
    const DEFAULT_ANIMATION_SPEED: AnimationSpeed = 'normal';
    const DEFAULT_INTERFACE_SCALE_PERCENT: InterfaceScalePercent = 100;
    const INTERFACE_SCALE_PERCENT_STEPS: readonly InterfaceScalePercent[] = [50, 75, 100, 125, 150];

    const isThemePreference = (value: string): value is ThemePreference => {
        if (value === 'light' || value === 'dark' || value === 'auto') {
            return true;
        }
        return false;
    };

    const isAnimationSpeed = (value: string): value is AnimationSpeed => {
        if (value === 'normal' || value === 'fast') {
            return true;
        }
        return false;
    };

    const isInterfaceScalePercent = (value: number): value is InterfaceScalePercent => INTERFACE_SCALE_PERCENT_STEPS.some((step) => step === value);

    const getGlobalScope = (): Window | null => (typeof window !== 'undefined' ? window : null);

    const preinitIssueReporter = {
        report: (reason: string): void => {
            const root = getGlobalScope()?.document?.documentElement;
            if (!(root instanceof HTMLElement)) {
                return;
            }
            if (!root.dataset['soaiThemePreinitIssue']) {
                root.dataset['soaiThemePreinitIssue'] = reason;
            }
        }
    };

    const safeGetLocalStorage = (scope: Window): Storage | null => {
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

    const normalizeStoredScalar = (value: string | null): string | null => {
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

    const normalizeStoredPreference = (value: string | null): ThemePreference | null => {
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

    const normalizeStoredAnimationSpeed = (value: string | null): AnimationSpeed | null => {
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

    const normalizeStoredInterfaceScale = (value: string | null): InterfaceScalePercent | null => {
        const normalizedValue = normalizeStoredScalar(value);
        if (!normalizedValue) {
            return null;
        }
        const numericValue = Number(normalizedValue);
        return isInterfaceScalePercent(numericValue) ? numericValue : null;
    };

    const readThemePreference = (scope: Window | null): ThemePreference => {
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

    const readAnimationSpeed = (scope: Window | null): AnimationSpeed => {
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

    const readInterfaceScale = (scope: Window | null): InterfaceScalePercent => {
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

    const resolveTheme = (scope: Window | null, preference: ThemePreference): ResolvedTheme => {
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

    const applyTheme = (root: HTMLElement, preference: ThemePreference, actualTheme: ResolvedTheme): void => {
        root.classList.remove('theme-dark', 'theme-light');
        root.classList.add(`theme-${actualTheme}`);
        root.dataset['soaiThemePreference'] = preference;
        root.style.setProperty('color-scheme', actualTheme);
    };

    const applyAnimationSpeed = (root: HTMLElement, speed: AnimationSpeed): void => {
        root.setAttribute(ANIMATION_SPEED_ATTRIBUTE, speed);
    };

    const applyInterfaceScale = (root: HTMLElement, percent: InterfaceScalePercent): void => {
        root.setAttribute(INTERFACE_SCALE_ATTRIBUTE, String(percent));
    };

    const initializeTheme = (): void => {
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

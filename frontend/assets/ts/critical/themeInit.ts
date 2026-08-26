/* SoAI - Critical frontend theme initialization [frontend/assets/ts/critical/themeInit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocumentElement, getMatchMedia } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ANIMATION_SPEED_ATTRIBUTE, ANIMATION_SPEED_STORAGE_KEY, DEFAULT_ANIMATION_SPEED, isAnimationSpeed, type AnimationSpeed } from '@core/animations/speed.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { readStorageText } from '@core/storage/ttlStorageCache.ts';
import { isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

type ThemePreference = 'light' | 'dark' | 'auto';
type ResolvedTheme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'soai.ui.theme';
const DEFAULT_THEME: ResolvedTheme = 'dark';
let themePreferenceFallbackWarned = false;
let animationSpeedFallbackWarned = false;

const warnThemePreferenceFallbackOnce = (detail: string): void => {
    if (themePreferenceFallbackWarned) {
        return;
    }
    themePreferenceFallbackWarned = true;
    errorHandler.warn('ThemeInit', `Theme preference fallback to default theme (${detail})`);
};

const warnAnimationSpeedFallbackOnce = (detail: string): void => {
    if (animationSpeedFallbackWarned) {
        return;
    }
    animationSpeedFallbackWarned = true;
    errorHandler.warn('ThemeInit', `Animation speed fallback to default (${detail})`);
};

const normalizeStoredPreference = (value: string): ThemePreference | null => {
    if (!isString(value)) {
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
    const lowered = toTrimmedLower(normalizedValue);
    if (lowered === 'light' || lowered === 'dark' || lowered === 'auto') {
        return lowered;
    }
    return null;
};

const normalizeStoredAnimationSpeed = (value: string): AnimationSpeed | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed.length) {
        return null;
    }
    const normalizedValue = trimmed.startsWith('"') && trimmed.endsWith('"') ? trimmed.slice(1, -1).trim() : trimmed;
    const lowered = toTrimmedLower(normalizedValue);
    return isAnimationSpeed(lowered) ? lowered : null;
};

const getStoredPreference = (): ThemePreference => {
    try {
        const stored = readStorageText('localStorage', THEME_STORAGE_KEY);
        if (stored === null) {
            return DEFAULT_THEME;
        }
        const normalized = normalizeStoredPreference(stored);
        if (isString(normalized)) {
            return normalized;
        }
        if (isString(stored) && stored.trim().length > 0) {
            warnThemePreferenceFallbackOnce('invalid stored value');
        }
    } catch (error) {
        ensureError(error);
        warnThemePreferenceFallbackOnce('storage read failed');
        return DEFAULT_THEME;
    }
    return DEFAULT_THEME;
};

const getStoredAnimationSpeed = (): AnimationSpeed => {
    try {
        const stored = readStorageText('localStorage', ANIMATION_SPEED_STORAGE_KEY);
        if (stored === null) {
            return DEFAULT_ANIMATION_SPEED;
        }
        const normalized = normalizeStoredAnimationSpeed(stored);
        if (isAnimationSpeed(normalized)) {
            return normalized;
        }
        if (isString(stored) && stored.trim().length > 0) {
            warnAnimationSpeedFallbackOnce('invalid stored value');
        }
    } catch (error) {
        ensureError(error);
        warnAnimationSpeedFallbackOnce('storage read failed');
        return DEFAULT_ANIMATION_SPEED;
    }
    return DEFAULT_ANIMATION_SPEED;
};

const resolveTheme = (preference: ThemePreference | string): ResolvedTheme => {
    const normalized = isString(preference) ? preference : DEFAULT_THEME;
    if (normalized === 'light') {
        return 'light';
    }
    if (normalized === 'auto') {
        const matchMedia = getMatchMedia();
        return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return DEFAULT_THEME;
};

export const applyThemePreference = (): ResolvedTheme => {
    const root = getDocumentElement();
    const preference = getStoredPreference();
    const actual = resolveTheme(preference);
    root.classList.remove('theme-dark', 'theme-light');
    root.classList.add(`theme-${actual}`);
    root.dataset['soaiThemePreference'] = isString(preference) ? preference : actual;
    root.style.setProperty('color-scheme', actual);
    root.setAttribute(ANIMATION_SPEED_ATTRIBUTE, getStoredAnimationSpeed());
    return actual;
};

export const initializeThemePreference = (): void => {
    try {
        applyThemePreference();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ThemeInit', 'Failed to apply theme preference; falling back to default theme', runtimeError);
        try {
            const root = getDocumentElement();
            root.classList.add('theme-dark');
            root.style.setProperty('color-scheme', 'dark');
            root.setAttribute(ANIMATION_SPEED_ATTRIBUTE, DEFAULT_ANIMATION_SPEED);
        } catch (fallbackError) {
            const fallbackRuntimeError = ensureError(fallbackError);
            errorHandler.warn('ThemeInit', 'Failed to apply fallback theme', fallbackRuntimeError);
        }
    }
};

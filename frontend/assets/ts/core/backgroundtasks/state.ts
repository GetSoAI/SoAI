/* SoAI - Shared background tasks state [frontend/assets/ts/core/backgroundtasks/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampInteger } from '@core/primitives/clampNumber.ts';
import type { BackgroundRoute } from '@core/backgroundtasks/types.ts';
import { isArray, isNumber, isString } from '@core/typeGuards.ts';
import { dom } from '@core/dom/dom.ts';
import { DEFAULT_OVERLAY_VALUE, MAX_OVERLAY_PERCENT, MIN_OVERLAY_PERCENT } from '@core/backgroundtasks/constants.ts';

const isValidCssColor = (color: string): boolean => {
    if (!color.trim()) {
        return false;
    }
    const trimmed = color.trim();
    const hexPattern = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6,8})$/;
    const rgbPattern = /^rgba?\(\s*(?:\d{1,3}\s*(?:,\s*\d{1,3}\s*){2}|%\s*(?:,\s*%\s*){2})\s*(?:,\s*[0-9.]+\s*)?\)$/;
    const hslPattern = /^hsla?\(\s*(?:[0-9.]+\s*(?:,\s*[0-9.]+%\s*){2}|deg\s*(?:,\s*[0-9.]+%\s*){2})\s*(?:,\s*[0-9.]+\s*)?\)$/;
    return hexPattern.test(trimmed) || rgbPattern.test(trimmed) || hslPattern.test(trimmed);
};

const normalizeOverlayValue = (value: number): number => {
    if (isNumber(value) && !Number.isNaN(value)) {
        return clampInteger(value, DEFAULT_OVERLAY_VALUE, MIN_OVERLAY_PERCENT, MAX_OVERLAY_PERCENT);
    }
    if (isString(value)) {
        const parsed = parseFloat(value);
        if (!Number.isNaN(parsed)) {
            return clampInteger(parsed, DEFAULT_OVERLAY_VALUE, MIN_OVERLAY_PERCENT, MAX_OVERLAY_PERCENT);
        }
    }
    return DEFAULT_OVERLAY_VALUE;
};

const normalizeRoute = (route: BackgroundRoute | undefined): string => {
    if (!route) {
        return '';
    }

    let source: string;
    if (typeof route === 'string') {
        source = route;
    } else {
        const descriptor = route;
        if (isString(descriptor['path']) && descriptor['path'].trim()) {
            source = descriptor['path'];
        } else if (isString(descriptor.component) && descriptor.component.trim()) {
            source = descriptor.component;
        } else if (isString(descriptor.name) && descriptor.name.trim()) {
            source = descriptor.name;
        } else if (isString(descriptor.pageId) && descriptor.pageId.trim()) {
            source = descriptor.pageId;
        } else if (isString(descriptor.id) && descriptor.id.trim()) {
            source = descriptor.id;
        } else {
            const rendered = descriptor.toString();
            source = isString(rendered) ? rendered : '';
        }
    }

    const trimmed = source.trim();
    if (!trimmed) {
        return '';
    }

    const withoutHash = trimmed.replace(/^#/, '');
    const [path] = withoutHash.split('?');
    if (!path) {
        return '';
    }

    const [base] = path.split('/');
    return (base ?? '').toLowerCase();
};

const hasLoadableContent = (container: HTMLElement): boolean => {
    const hasElements = container.childElementCount > 0;
    const spinner = dom.resolve('.spinner', container);
    const textContent = container.textContent;
    if (!isString(textContent)) {
        throw new Error('Main content container must expose textContent');
    }
    const hasLoadingText = textContent.trim().toLowerCase().includes('loading');
    return hasElements && !spinner && !hasLoadingText;
};

const hasWallpaperFiles = (value: string[] | null | undefined): boolean => isArray(value);

export { hasLoadableContent, hasWallpaperFiles, isValidCssColor, normalizeOverlayValue, normalizeRoute };

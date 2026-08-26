/* SoAI - Charts feature chart color analysis [frontend/assets/ts/features/charts/component/chartColorAnalysis.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { ChartColorComponentInput, ChartColorInput } from '@features/charts/chartTypes.ts';
import { isFin, normalizeAlpha, normalizeHue, normalizePercent, normalizeRgb } from '@features/charts/component/chartComponentStatics.ts';
import type { ColorComponents } from '@features/charts/component/chartComponentTypes.ts';

const parseColorComponents = (color: ChartColorInput): ColorComponents | null => {
    if (!color) {
        return null;
    }
    if (isObject(color)) {
        const redChannel = color['r'];
        const greenChannel = color['g'];
        const blueChannel = color['b'];
        const alphaValue = color['a'] ?? 1;
        if (![redChannel, greenChannel, blueChannel].every(isFin)) {
            return null;
        }
        const alphaCandidate = Number(alphaValue);
        const normalizedAlpha = isFin(alphaCandidate) ? alphaCandidate : 1;
        return {
            red: clampNumber(Math.round(Number(redChannel)), 0, 255),
            green: clampNumber(Math.round(Number(greenChannel)), 0, 255),
            blue: clampNumber(Math.round(Number(blueChannel)), 0, 255),
            alpha: clampNumber(normalizedAlpha, 0, 1)
        };
    }
    const input = String(color).trim();
    if (!input) {
        return null;
    }
    if (input.startsWith('#')) {
        let hex = input.slice(1);
        if (hex.length === 3 || hex.length === 4) {
            hex = [...hex].map((ch) => ch + ch).join('');
        }
        if (hex.length === 6 || hex.length === 8) {
            const redChannel = parseInt(hex.slice(0, 2), 16);
            const greenChannel = parseInt(hex.slice(2, 4), 16);
            const blueChannel = parseInt(hex.slice(4, 6), 16);
            const alpha = hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1;
            if ([redChannel, greenChannel, blueChannel].some(Number.isNaN)) {
                return null;
            }
            return { red: redChannel, green: greenChannel, blue: blueChannel, alpha: clampNumber(alpha, 0, 1) };
        }
        return null;
    }
    const match = input.match(/^(rgba?|hsla?)\(([^)]+)\)/i);
    if (!match) {
        return null;
    }
    const type = match[1] ?? '';
    const value = match[2] ?? '';
    const segments = value.replace(/[,/]/g, ' ').trim().split(/\s+/).filter(Boolean);
    if (type.startsWith('rgb')) {
        const redChannel = normalizeRgb(segments[0] ?? null);
        const greenChannel = normalizeRgb(segments[1] ?? null);
        const blueChannel = normalizeRgb(segments[2] ?? null);
        if (redChannel === null || greenChannel === null || blueChannel === null) {
            return null;
        }
        return { red: redChannel, green: greenChannel, blue: blueChannel, alpha: normalizeAlpha(segments[3] ?? null) };
    }
    if (type.startsWith('hsl')) {
        const height = normalizeHue(segments[0]);
        const stringValue = normalizePercent(segments[1]);
        const leftValue = normalizePercent(segments[2]);
        if (!isFiniteNumber(height) || isNullOrUndefined(stringValue) || isNullOrUndefined(leftValue)) {
            return null;
        }
        const hue = (((height % 360) + 360) % 360) / 360;
        const sValue = stringValue;
        const lValue = leftValue;
        const query = lValue < 0.5 ? lValue * (1 + sValue) : lValue + sValue - lValue * sValue;
        const point = 2 * lValue - query;
        const h2rgb = (key: number): number => {
            const wrapped = key < 0 ? key + 1 : key > 1 ? key - 1 : key;
            if (wrapped < 1 / 6) return point + (query - point) * 6 * wrapped;
            if (wrapped < 0.5) return query;
            if (wrapped < 2 / 3) return point + (query - point) * (2 / 3 - wrapped) * 6;
            return point;
        };
        return {
            red: Math.round(h2rgb(hue + 1 / 3) * 255),
            green: Math.round(h2rgb(hue) * 255),
            blue: Math.round(h2rgb(hue - 1 / 3) * 255),
            alpha: normalizeAlpha(segments[3])
        };
    }
    return null;
};

const calculateLuminance = (components: ColorComponents): number => {
    const transform = (value: number): number => {
        const normalized = value / 255;
        return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * transform(components.red) + 0.7152 * transform(components.green) + 0.0722 * transform(components.blue);
};

const calculateContrast = (l1: number, l2: number): number | null => {
    const n1 = l1;
    const n2 = l2;
    if (!isFin(n1) || !isFin(n2)) {
        return null;
    }
    return (Math.max(n1, n2) + 0.05) / (Math.min(n1, n2) + 0.05);
};

const normalizeBackgroundColor = (color: string | null | undefined, isDark: boolean, parse: (color: ChartColorComponentInput | string | null | undefined) => ColorComponents | null): string => {
    const fallback = isDark ? 'rgba(15, 23, 42, 0.88)' : '#ffffff';
    if (!color || color === 'transparent' || color === 'none') {
        return fallback;
    }
    const components = parse(color);
    if (!components) {
        return fallback;
    }
    const { red: redChannel, green: greenChannel, blue: blueChannel, alpha } = components;
    if (!isDark) {
        if (alpha < 0.95) {
            return fallback;
        }
        if ((redChannel + greenChannel + blueChannel) / 765 > 0.85 && Math.max(redChannel, greenChannel, blueChannel) - Math.min(redChannel, greenChannel, blueChannel) < 18) {
            return fallback;
        }
    } else if (redChannel === 255 && greenChannel === 255 && blueChannel === 255) {
        return fallback;
    }
    return String(color);
};

export type { ColorComponents };
export { parseColorComponents, calculateLuminance, calculateContrast, normalizeBackgroundColor };

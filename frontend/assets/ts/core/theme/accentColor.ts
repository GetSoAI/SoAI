/* SoAI - Accent color normalization and DOM application [frontend/assets/ts/core/theme/accentColor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { formatHexColor, hslToRgb, parseHexColor, rgbToHsl, type HslColor, type RgbColor } from '@core/theme/colorSpace.ts';
import { normalizeRuntimeHexColorCanonicalOrNull } from '@core/theme/hexColor.ts';

type AccentColorTargets = { root: HTMLElement; body?: HTMLElement | null };

const computeAccentVariants = (base: string): { light: string; dark: string } => {
    const baseRgb = parseHexColor(base);
    const baseHsl = rgbToHsl(baseRgb);
    const light: HslColor = {
        hue: baseHsl.hue,
        saturation: Math.min(1, baseHsl.saturation * 1.03),
        lightness: Math.min(0.88, baseHsl.lightness + 0.18)
    };
    const dark: HslColor = {
        hue: baseHsl.hue,
        saturation: Math.min(1, baseHsl.saturation * 1.02),
        lightness: Math.max(0.16, baseHsl.lightness - 0.18)
    };

    return {
        light: formatHexColor(hslToRgb(light)).toLowerCase(),
        dark: formatHexColor(hslToRgb(dark)).toLowerCase()
    };
};

const linearizeChannel = (channel: number): number => {
    const normalized = channel / 255;
    if (normalized <= 0.03928) {
        return normalized / 12.92;
    }
    return Math.pow((normalized + 0.055) / 1.055, 2.4);
};

const relativeLuminance = ({ red, green, blue }: RgbColor): number => {
    const redLuminance = linearizeChannel(red);
    const greenLuminance = linearizeChannel(green);
    const blueLuminance = linearizeChannel(blue);
    return 0.2126 * redLuminance + 0.7152 * greenLuminance + 0.0722 * blueLuminance;
};

const contrastRatio = (left: number, right: number): number => {
    const lighter = Math.max(left, right);
    const darker = Math.min(left, right);
    return (lighter + 0.05) / (darker + 0.05);
};

const computeTextOnAccent = (base: string): '#000000' | '#ffffff' => {
    const luminance = relativeLuminance(parseHexColor(base));
    const contrastWithBlack = contrastRatio(luminance, 0);
    const contrastWithWhite = contrastRatio(luminance, 1);
    return contrastWithBlack >= contrastWithWhite ? '#000000' : '#ffffff';
};

const normalizeAccentColorPreference = (value: JsonValue | undefined): string | null => {
    return normalizeRuntimeHexColorCanonicalOrNull(value);
};

const applyAccentColorToElement = (element: HTMLElement, value: string | null): void => {
    const normalized = normalizeAccentColorPreference(value);
    const style = element.style;

    if (!normalized) {
        style.removeProperty('--accent-green');
        style.removeProperty('--accent-green-light');
        style.removeProperty('--accent-green-dark');
        style.removeProperty('--text-on-accent');
        return;
    }

    const variants = computeAccentVariants(normalized);
    style.setProperty('--accent-green', normalized);
    style.setProperty('--accent-green-light', variants.light);
    style.setProperty('--accent-green-dark', variants.dark);
    style.setProperty('--text-on-accent', computeTextOnAccent(normalized));
};

const applyAccentColor = ({ root, body }: AccentColorTargets, value: string | null): void => {
    applyAccentColorToElement(root, value);
    if (body && body !== root) {
        applyAccentColorToElement(body, value);
    }
};

export { applyAccentColor, normalizeAccentColorPreference };

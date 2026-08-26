/* SoAI - Color space conversion helpers [frontend/assets/ts/core/theme/colorSpace.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampFiniteNumber, clampNumber } from '@core/primitives/clampNumber.ts';
import { normalizeHexColorCanonicalOrNull } from '@core/theme/hexColor.ts';

type RgbColor = { red: number; green: number; blue: number };
type HslColor = { hue: number; saturation: number; lightness: number };

const clamp01 = (value: number): number => {
    return clampFiniteNumber(value, 0, 0, 1);
};

const parseHexColor = (hex: string): RgbColor => {
    const normalized = normalizeHexColorCanonicalOrNull(hex);
    if (!normalized) {
        throw new Error('Invalid hex color');
    }
    const rawHex = normalized.slice(1);
    if (rawHex.length !== 6) {
        throw new Error('Expected 6-digit hex color');
    }
    const red = Number.parseInt(rawHex.slice(0, 2), 16);
    const green = Number.parseInt(rawHex.slice(2, 4), 16);
    const blue = Number.parseInt(rawHex.slice(4, 6), 16);
    if (![red, green, blue].every((channel) => Number.isFinite(channel) && channel >= 0 && channel <= 255)) {
        throw new Error('Invalid RGB channels parsed from hex color');
    }
    return { red, green, blue };
};

const toHexChannel = (value: number): string => {
    const clamped = clampNumber(Math.round(value), 0, 255);
    return clamped.toString(16).padStart(2, '0');
};

const formatHexColor = ({ red, green, blue }: RgbColor): string => {
    return `#${toHexChannel(red)}${toHexChannel(green)}${toHexChannel(blue)}`;
};

const rgbToHsl = ({ red, green, blue }: RgbColor): HslColor => {
    const normalizedRed = red / 255;
    const normalizedGreen = green / 255;
    const normalizedBlue = blue / 255;
    const maximumChannel = Math.max(normalizedRed, normalizedGreen, normalizedBlue);
    const minimumChannel = Math.min(normalizedRed, normalizedGreen, normalizedBlue);
    const channelSpread = maximumChannel - minimumChannel;
    const lightness = (maximumChannel + minimumChannel) / 2;

    if (channelSpread === 0) {
        return { hue: 0, saturation: 0, lightness };
    }

    const saturation = lightness > 0.5 ? channelSpread / (2 - maximumChannel - minimumChannel) : channelSpread / (maximumChannel + minimumChannel);
    let hue = 0;
    if (maximumChannel === normalizedRed) {
        hue = (normalizedGreen - normalizedBlue) / channelSpread + (normalizedGreen < normalizedBlue ? 6 : 0);
    } else if (maximumChannel === normalizedGreen) {
        hue = (normalizedBlue - normalizedRed) / channelSpread + 2;
    } else {
        hue = (normalizedRed - normalizedGreen) / channelSpread + 4;
    }
    hue /= 6;
    return { hue, saturation, lightness };
};

const hueToRgb = (lowerComponent: number, upperComponent: number, hueOffsetInput: number): number => {
    let hueOffset = hueOffsetInput;
    if (hueOffset < 0) hueOffset += 1;
    if (hueOffset > 1) hueOffset -= 1;
    if (hueOffset < 1 / 6) return lowerComponent + (upperComponent - lowerComponent) * 6 * hueOffset;
    if (hueOffset < 1 / 2) return upperComponent;
    if (hueOffset < 2 / 3) return lowerComponent + (upperComponent - lowerComponent) * (2 / 3 - hueOffset) * 6;
    return lowerComponent;
};

const hslToRgb = ({ hue, saturation, lightness }: HslColor): RgbColor => {
    const normalizedHue = clamp01(hue);
    const normalizedSaturation = clamp01(saturation);
    const normalizedLightness = clamp01(lightness);

    if (normalizedSaturation === 0) {
        const neutralChannel = normalizedLightness * 255;
        return { red: neutralChannel, green: neutralChannel, blue: neutralChannel };
    }

    const upperComponent = normalizedLightness < 0.5 ? normalizedLightness * (1 + normalizedSaturation) : normalizedLightness + normalizedSaturation - normalizedLightness * normalizedSaturation;
    const lowerComponent = 2 * normalizedLightness - upperComponent;
    const red = hueToRgb(lowerComponent, upperComponent, normalizedHue + 1 / 3) * 255;
    const green = hueToRgb(lowerComponent, upperComponent, normalizedHue) * 255;
    const blue = hueToRgb(lowerComponent, upperComponent, normalizedHue - 1 / 3) * 255;
    return { red, green, blue };
};

export { formatHexColor, hslToRgb, parseHexColor, rgbToHsl };
export type { HslColor, RgbColor };

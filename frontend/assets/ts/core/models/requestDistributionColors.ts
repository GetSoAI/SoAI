/* SoAI - Shared models request distribution colors [frontend/assets/ts/core/models/requestDistributionColors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const parseHexColor = (hex: string): { red: number; green: number; blue: number } | null => {
    const trimmed = hex.trim();
    if (trimmed.length !== 7 || trimmed.charAt(0) !== '#') {
        return null;
    }
    const red = Number.parseInt(trimmed.slice(1, 3), 16);
    const green = Number.parseInt(trimmed.slice(3, 5), 16);
    const blue = Number.parseInt(trimmed.slice(5, 7), 16);
    if (!Number.isFinite(red) || !Number.isFinite(green) || !Number.isFinite(blue)) {
        return null;
    }
    return { red, green, blue };
};

const clampChannel = (value: number): number => {
    if (value < 0) {
        return 0;
    }
    if (value > 255) {
        return 255;
    }
    return Math.round(value);
};

const toHexChannel = (value: number): string => {
    const hex = clampChannel(value).toString(16);
    return hex.length === 1 ? `0${hex}` : hex;
};

const adjustHexColor = (hex: string, factor: number, towardWhite: boolean): string => {
    const parsed = parseHexColor(hex);
    if (parsed === null) {
        return hex;
    }
    const transform = (channel: number): number => {
        if (towardWhite) {
            return channel + (255 - channel) * factor;
        }
        return channel * factor;
    };
    return `#${toHexChannel(transform(parsed.red))}${toHexChannel(transform(parsed.green))}${toHexChannel(transform(parsed.blue))}`;
};

const darkenHexColor = (hex: string, factor: number): string => {
    return adjustHexColor(hex, factor, false);
};

const lightenHexColor = (hex: string, factor: number): string => {
    return adjustHexColor(hex, factor, true);
};

const saturateHexColor = (hex: string, amount: number): string => {
    const parsed = parseHexColor(hex);
    if (parsed === null) {
        return hex;
    }
    const luminance = parsed.red * 0.299 + parsed.green * 0.587 + parsed.blue * 0.114;
    const push = (channel: number): number => channel + (channel - luminance) * amount;
    return `#${toHexChannel(push(parsed.red))}${toHexChannel(push(parsed.green))}${toHexChannel(push(parsed.blue))}`;
};

const toSurfaceColor = (hex: string): string => lightenHexColor(saturateHexColor(hex, 22 / 100), 6 / 100);

export { darkenHexColor, lightenHexColor, toSurfaceColor };

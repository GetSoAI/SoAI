/* SoAI - Hex color helpers [frontend/assets/ts/core/theme/hexColor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const HEX_COLOR_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

const isHexColorString = (value: string): boolean => {
    const trimmed = value.trim();
    if (!trimmed) {
        return false;
    }
    return HEX_COLOR_PATTERN.test(trimmed);
};

const trimHexColorOrNull = (value: string): string | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    return HEX_COLOR_PATTERN.test(trimmed) ? trimmed : null;
};

const expandShortHex = (hex3: string): string => {
    const raw = hex3.slice(1);
    if (raw.length !== 3) {
        throw new Error('Expected 3-digit hex color');
    }
    const [redChannel, greenChannel, secondValue] = raw.split('');
    if (!redChannel || !greenChannel || !secondValue) {
        throw new Error('Invalid 3-digit hex color');
    }
    return `#${redChannel}${redChannel}${greenChannel}${greenChannel}${secondValue}${secondValue}`;
};

const normalizeHexColorCanonicalOrNull = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    if (!HEX_COLOR_PATTERN.test(trimmed)) {
        return null;
    }
    const expanded = trimmed.length === 4 ? expandShortHex(trimmed) : trimmed;
    return expanded.toLowerCase();
};

const normalizeRuntimeHexColorCanonicalOrNull = (value: JsonValue | undefined): string | null => {
    if (!isString(value)) {
        return null;
    }
    return normalizeHexColorCanonicalOrNull(value);
};

export { isHexColorString, normalizeHexColorCanonicalOrNull, normalizeRuntimeHexColorCanonicalOrNull, trimHexColorOrNull };

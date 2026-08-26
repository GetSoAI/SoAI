/* SoAI - Shared primitives clamp number [frontend/assets/ts/core/primitives/clampNumber.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const clampNumber = (value: number, min: number | undefined, max: number | undefined): number => {
    let clamped = value;
    if (min !== undefined && clamped < min) {
        clamped = min;
    }
    if (max !== undefined && clamped > max) {
        clamped = max;
    }
    return clamped;
};

const clampFiniteNumber = (value: number, fallback: number, min: number | undefined, max: number | undefined): number => {
    const normalized = Number.isFinite(value) ? value : fallback;
    return clampNumber(normalized, min, max);
};

const clampInteger = (value: number, fallback: number, min: number | undefined, max: number | undefined): number => {
    const normalized = Number.isFinite(value) ? value : fallback;
    const minInteger = min === undefined ? undefined : Math.ceil(min);
    const maxInteger = max === undefined ? undefined : Math.floor(max);
    return clampNumber(Math.round(normalized), minInteger, maxInteger);
};

const clampNonNegative = (value: number, fallback: number = 0): number => {
    return clampFiniteNumber(value, fallback, 0, undefined);
};

const clampPercent = (value: number, fallback: number = 0): number => {
    return clampFiniteNumber(value, fallback, 0, 100);
};

export { clampFiniteNumber, clampInteger, clampNonNegative, clampNumber, clampPercent };

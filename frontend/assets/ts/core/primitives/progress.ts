/* SoAI - Shared primitives progress [frontend/assets/ts/core/primitives/progress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isNullOrUndefined, isNumber, isString } from '@core/typeGuards.ts';

const parseProgressNumber = (value: string): number | null => {
    const trimmed = value.trim();
    const normalized = trimmed.endsWith('%') ? trimmed.slice(0, -1).trim() : trimmed;
    if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(normalized)) {
        return null;
    }
    const numericValue = Number(normalized);
    return isFiniteNumber(numericValue) ? numericValue : null;
};

export const normalizeProgress = (value: JsonValue | undefined): number | null => {
    if (isNullOrUndefined(value)) return null;
    const number = isString(value) ? parseProgressNumber(value) : value;
    return isFiniteNumber(number) ? Math.round(clampPercent(number < 1 && number >= 0 ? number * 100 : number)) : null;
};

export const normalizeProgressPercent = (value: JsonValue | undefined): number | null => {
    if (!isNumber(value)) return null;
    return Math.round(clampPercent(value));
};

export const normalizeProgressRatio = (value: JsonValue | undefined): number | null => {
    if (!isFiniteNumber(value)) return null;
    return Math.round(clampPercent(value * 100));
};

export const normalizeProgressParts = (completed: JsonValue | undefined, total: JsonValue | undefined): number | null => {
    if (!isFiniteNumber(completed) || !isFiniteNumber(total) || total <= 0 || completed <= 0) return null;
    return normalizeProgressRatio(completed / total);
};

export const normalizeProgressCompletedTotal = (completed: JsonValue | undefined, total: JsonValue | undefined): number | null => {
    if (!isFiniteNumber(completed) || !isFiniteNumber(total) || total <= 0 || completed < 0) return null;
    return normalizeProgressRatio(completed / total);
};

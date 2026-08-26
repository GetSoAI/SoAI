/* SoAI - Charts feature data transforms validation [frontend/assets/ts/features/charts/datatransforms/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { MIN_RETENTION_MINUTES } from '@features/charts/datatransforms/constants.ts';

const normalizeMinutesValue = (value: number | null | undefined, defaultValue: number | null = null, { minimum = MIN_RETENTION_MINUTES }: { minimum?: number } = {}): number | null => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    if (!Number.isFinite(numeric) || numeric === null) {
        return defaultValue;
    }
    return Math.max(minimum, Math.round(numeric));
};

const normalizeMinutesList = (values: readonly number[], { minimum = 1 }: { minimum?: number } = {}): number[] => {
    if (!values.length) {
        return [];
    }
    const normalized = values.map((value: number): number | null => normalizeMinutesValue(value, null, { minimum })).filter((value: number | null): value is number => Number.isFinite(value) && value !== null);
    return Array.from(new Set(normalized)).sort((firstValue: number, secondValue: number): number => firstValue - secondValue);
};

const ensureMinutesOption = (options: number[], candidate: number | null, { minimum = 1 }: { minimum?: number } = {}): number[] => {
    const list = [...options];
    const normalized = normalizeMinutesValue(candidate, null, { minimum });
    if (!Number.isFinite(normalized) || normalized === null) {
        return normalizeMinutesList(list, { minimum });
    }
    if (!list.includes(normalized)) {
        list.push(normalized);
    }
    return normalizeMinutesList(list, { minimum });
};

const resolveSupportedIntervalMs = (targetMs: number, supportedIntervalsMs: number[] | null | undefined, defaultMs: number): number => {
    const defaultValue = readCoercedFiniteNumberOrNullValue(defaultMs);
    const defaultInterval = defaultValue !== null && defaultValue > 0 ? Math.round(defaultValue) : null;

    const candidates =
        isArray(supportedIntervalsMs) && supportedIntervalsMs.length
            ? Array.from(
                  new Set(
                      supportedIntervalsMs
                          .map((value: number): number | null => {
                              const numeric = readCoercedFiniteNumberOrNullValue(value);
                              return numeric !== null && numeric > 0 ? Math.round(numeric) : null;
                          })
                          .filter((value: number | null): value is number => Number.isFinite(value) && value !== null)
                  )
              ).sort((firstValue: number, secondValue: number): number => firstValue - secondValue)
            : [];

    if (!candidates.length) {
        const desiredValue = readCoercedFiniteNumberOrNullValue(targetMs);
        const desired = desiredValue !== null && desiredValue > 0 ? Math.round(desiredValue) : null;
        if (desired) {
            return desired;
        }
        return defaultInterval || 60_000;
    }

    const desiredValue = readCoercedFiniteNumberOrNullValue(targetMs);
    const desired = desiredValue !== null && desiredValue > 0 ? Math.round(desiredValue) : null;
    if (desired) {
        for (const candidate of candidates) {
            if (candidate >= desired) {
                return candidate;
            }
        }
    }

    const last = candidates[candidates.length - 1];
    return last !== undefined ? last : 60_000;
};

export { ensureMinutesOption, normalizeMinutesList, normalizeMinutesValue, resolveSupportedIntervalMs };

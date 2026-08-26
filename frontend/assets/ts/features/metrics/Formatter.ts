/* SoAI - Metrics feature formatter [frontend/assets/ts/features/metrics/Formatter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatEpochMsTimeSecondOrEmpty } from '@core/primitives/dateTime.ts';
import { formatCompactMillisecondsAsSecondsUnit } from '@core/primitives/duration.ts';
import { filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';

interface MetricsFormattingApi {
    formatNumber?(value: number): string;
    formatRelativeTime?(timestamp: number): string;
}

interface MetricsFormatterOptions {
    formatting?: MetricsFormattingApi;
}

class MetricsFormatter {
    #formatting: MetricsFormattingApi | null;

    constructor({ formatting }: MetricsFormatterOptions = {}) {
        this.#formatting = formatting ?? null;
    }

    number<T extends JsonValue | null | undefined>(value: T, fallback: string = i18n.t('common.notAvailableShort')): string {
        if (isString(value)) {
            const trimmed = value.trim();
            return trimmed || fallback;
        }
        if (!isFiniteNumber(value)) return fallback;
        const formatNumber = this.#formatting?.formatNumber;
        const formatted = typeof formatNumber === 'function' ? formatNumber(value) : null;
        if (isString(formatted) && formatted.trim()) return formatted;
        return i18n.formatNumber(value);
    }

    rounded<T extends JsonValue | null | undefined>(value: T, fallback: string = i18n.t('common.notAvailableShort')): string {
        if (!isFiniteNumber(value)) return fallback;
        return this.number(Math.round(value), fallback);
    }

    ms<T extends JsonValue | null | undefined>(value: T, fallback: string = i18n.t('common.notAvailableShort')): string {
        if (!isFiniteNumber(value)) return fallback;
        return i18n.t('common.time.units.millisecond.short', { count: Math.round(value) });
    }

    secondsFromMs<T extends JsonValue | null | undefined>(value: T, fallback: string = i18n.t('common.notAvailableShort')): string {
        if (!isFiniteNumber(value)) return fallback;
        return formatCompactMillisecondsAsSecondsUnit(value);
    }

    list<T extends JsonValue | null | undefined>(values: T, fallback: string = ''): string {
        const filtered = filterTrimmedStringArrayValue(values);
        return filtered.length ? filtered.join(', ') : fallback;
    }

    relativeTime<T extends JsonValue | null | undefined>(timestamp: T): string {
        if (!isFiniteNumber(timestamp)) return '';
        const formatRelativeTime = this.#formatting?.formatRelativeTime;
        if (typeof formatRelativeTime === 'function') {
            const relative = formatRelativeTime(timestamp);
            if (relative) return relative;
        }
        return formatEpochMsTimeSecondOrEmpty(timestamp);
    }

    text<T extends JsonValue | null | undefined>(value: T, fallback: string): string {
        if (isString(value)) {
            const trimmed = value.trim();
            if (trimmed) return trimmed;
        }
        return fallback;
    }

    pendingLabel(): string {
        return i18n.t('metrics.cards.frontendMetrics.values.pending');
    }

    unknownLabel(): string {
        return i18n.t('metrics.cards.frontendMetrics.values.unknown');
    }
}

export { MetricsFormatter };
export type { MetricsFormattingApi, MetricsFormatterOptions };

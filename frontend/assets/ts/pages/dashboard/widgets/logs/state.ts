/* SoAI - Dashboard page logs state [frontend/assets/ts/pages/dashboard/widgets/logs/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FONT_SCALE_RANGE, LOG_LINE_LIMIT_DEFAULT, LOG_LINE_LIMIT_RANGE, LOG_LINE_LIMIT_STORAGE_KEY } from '@pages/dashboard/widgets/logs/constants.ts';
import type { DashboardLogsLineLimitStorage } from '@pages/dashboard/widgets/logs/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

class DashboardLogsState {
    readonly #storage: DashboardLogsLineLimitStorage;
    #autoScroll = true;
    #fontScale = 0.75;
    #lineLimit: number;

    constructor(storage: DashboardLogsLineLimitStorage) {
        this.#storage = storage;
        this.#lineLimit = this.#loadLineLimit();
    }

    get autoScroll(): boolean {
        return this.#autoScroll;
    }

    get fontScale(): number {
        return this.#fontScale;
    }

    get lineLimit(): number {
        return this.#lineLimit;
    }

    static clampValue(value: JsonValue, min: number, max: number): number {
        const numeric: number = Number(value);
        if (!isFiniteNumber(numeric)) {
            return min;
        }
        if (numeric < min) {
            return min;
        }
        if (numeric > max) {
            return max;
        }
        return numeric;
    }

    #loadLineLimit(): number {
        const raw: number = Number(this.#storage.storageGet('soai_log_line_limit', LOG_LINE_LIMIT_DEFAULT));
        const normalized: number = DashboardLogsState.clampValue(raw, LOG_LINE_LIMIT_RANGE.min, LOG_LINE_LIMIT_RANGE.max);
        if (normalized !== raw) {
            this.#storage.storageSet(LOG_LINE_LIMIT_STORAGE_KEY, normalized);
        }
        return normalized;
    }

    adjustFont(delta: number): number {
        this.#fontScale = DashboardLogsState.clampValue(this.#fontScale + delta, FONT_SCALE_RANGE.min, FONT_SCALE_RANGE.max);
        return this.#fontScale;
    }

    toggleAutoScroll(): boolean {
        this.#autoScroll = !this.#autoScroll;
        return this.#autoScroll;
    }
}

export { DashboardLogsState };

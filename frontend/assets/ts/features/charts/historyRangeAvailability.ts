/* SoAI - Charts feature history range availability [frontend/assets/ts/features/charts/historyRangeAvailability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { HistoryAvailability } from '@core/realtime/historyAvailabilityContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import type { TimeRangeSelection } from '@features/charts/controlsTypes.ts';

type HistoryRangeAvailabilityStatus = 'pending' | 'ready' | 'failed';

interface AvailableTimeRangesInput {
    options: readonly number[];
    availability: HistoryAvailability;
    loggingIntervalMs: number;
}

interface AvailableTimeRanges {
    options: number[];
    nextCheckAtMs: number | null;
}

type HistoryAvailabilitySettlement = 'stale' | 'unchanged' | 'corrected';

interface SettleHistoryAvailabilityOptions {
    rangeAvailability: HistoryRangeAvailability;
    seriesKey: string;
    availability: HistoryAvailability | null;
    loggingIntervalMs: number;
    requestedRange: number;
    getTimeRange: () => number;
    syncTimeRange: () => Promise<boolean>;
    isCurrent: () => boolean;
}

type AcceptedAvailability = {
    seriesKey: string;
    availability: HistoryAvailability | null;
    loggingIntervalMs: number;
};

const resolveAvailableTimeRanges = ({ options, availability, loggingIntervalMs }: AvailableTimeRangesInput): AvailableTimeRanges => {
    const [smallest, ...larger] = options;
    if (smallest === undefined) {
        return { options: [], nextCheckAtMs: null };
    }
    const nowMs = availability.observedAtMs;
    const retentionOptionMinutes = options[options.length - 1];
    const cadenceMs = 2 * Math.max(0, loggingIntervalMs);
    const freshWindowMs = Math.max(minutesToMs(smallest), cadenceMs);
    const oldestMs = availability.oldestSampleTsMs;
    const newestMs = availability.newestSampleTsMs;
    const freshUntilMs = newestMs === null ? null : newestMs + freshWindowMs;
    const fresh = freshUntilMs !== null && nowMs < freshUntilMs;
    const available = [smallest];
    const checksAtMs = fresh ? [freshUntilMs] : [];
    for (const minutes of larger) {
        const unlockAtMs = oldestMs === null ? null : oldestMs + minutesToMs(minutes) - (minutes === retentionOptionMinutes ? cadenceMs : 0);
        if (fresh && unlockAtMs !== null && nowMs >= unlockAtMs) {
            available.push(minutes);
        } else {
            checksAtMs.push(fresh && unlockAtMs !== null ? unlockAtMs : nowMs + freshWindowMs);
        }
    }
    return { options: available, nextCheckAtMs: larger.length > 0 ? Math.min(...checksAtMs) : null };
};

const selectAvailableTimeRange = (options: readonly number[], savedMinutes: number): number => options.reduce((selected, minutes) => (minutes <= savedMinutes ? minutes : selected), options[0] ?? savedMinutes);

class HistoryRangeAvailability {
    readonly #timer: TimeoutTimer;
    #accepted: AcceptedAvailability | null = null;
    #scheduledCheckAtMs: number | null = null;
    #onRecheck: (() => void) | null;

    constructor(onRecheck: (() => void) | null = null) {
        this.#onRecheck = onRecheck;
        this.#timer = new TimeoutTimer(0, () => {
            const callback = this.#onRecheck;
            if (!callback) throw new Error('History availability recheck is not bound');
            callback();
        });
    }

    bindRecheck(onRecheck: () => void): void {
        if (this.#onRecheck) throw new Error('History availability recheck is already bound');
        this.#onRecheck = onRecheck;
    }

    status(seriesKey: string): HistoryRangeAvailabilityStatus {
        if (this.#accepted?.seriesKey !== seriesKey) {
            return 'pending';
        }
        return this.#accepted.availability ? 'ready' : 'failed';
    }

    accept(seriesKey: string, availability: HistoryAvailability | null, loggingIntervalMs: number): void {
        this.#accepted = { seriesKey, availability, loggingIntervalMs };
        this.#schedule(null);
    }

    resolveSelection(seriesKey: string, selection: TimeRangeSelection): TimeRangeSelection {
        const accepted = this.#accepted;
        if (accepted?.seriesKey !== seriesKey || !accepted.availability) {
            this.#schedule(null);
            return { options: selection.options.slice(0, 1), selected: selection.options[0] ?? selection.selected };
        }
        const available = resolveAvailableTimeRanges({ options: selection.options, availability: accepted.availability, loggingIntervalMs: accepted.loggingIntervalMs });
        this.#schedule(available.nextCheckAtMs);
        return { options: available.options, selected: selectAvailableTimeRange(available.options, selection.selected) };
    }

    reset(): void {
        this.#accepted = null;
        this.#schedule(null);
    }

    retryRecheck(delayMs: number): void {
        if (!Number.isFinite(delayMs) || delayMs <= 0) throw new TypeError('History availability retry delay must be positive');
        this.#schedule(serverEpochMs() + delayMs);
    }

    #schedule(nextCheckAtMs: number | null): void {
        if (nextCheckAtMs !== null && !this.#onRecheck) throw new Error('History availability recheck is not bound');
        if (nextCheckAtMs === this.#scheduledCheckAtMs) {
            return;
        }
        this.#scheduledCheckAtMs = nextCheckAtMs;
        if (nextCheckAtMs === null) {
            this.#timer.stop();
            return;
        }
        this.#timer.start(Math.max(0, nextCheckAtMs - serverEpochMs()));
    }
}

const settleHistoryAvailability = async (options: SettleHistoryAvailabilityOptions): Promise<HistoryAvailabilitySettlement> => {
    options.rangeAvailability.accept(options.seriesKey, options.availability, options.loggingIntervalMs);
    for (let attempt = 0; attempt < 4 && options.isCurrent(); attempt += 1) {
        if (!(await options.syncTimeRange())) {
            continue;
        }
        if (!options.isCurrent()) {
            return 'stale';
        }
        if (!options.availability) {
            throw new Error(i18n.t('charts.historyFailed'));
        }
        return options.getTimeRange() === options.requestedRange ? 'unchanged' : 'corrected';
    }
    if (options.isCurrent()) throw new Error('History timeframe controls did not settle');
    return 'stale';
};

export { HistoryRangeAvailability, resolveAvailableTimeRanges, selectAvailableTimeRange, settleHistoryAvailability };
export type { AvailableTimeRanges, HistoryAvailabilitySettlement, HistoryRangeAvailabilityStatus };

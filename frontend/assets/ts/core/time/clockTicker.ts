/* SoAI - Shared time clock ticker [frontend/assets/ts/core/time/clockTicker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ClockTickCadence = 'second' | 'minute';

interface ClockTickerTimers {
    setTimer: (callback: () => void, delay: number, options?: { repeat?: boolean }) => number | null;
    clearTimer: (id: number | null) => void;
}

interface ClockTickerOptions {
    timers: ClockTickerTimers;
    getCadence: () => ClockTickCadence | null;
    onTick: () => void;
}

const MIN_CLOCK_DELAY_MS = 16;
const SECOND_MS = 1000;
const MINUTE_SECONDS = 60;

const resolveClockTickDelayMs = (date: Date, cadence: ClockTickCadence): number => {
    const millisecondDelay = cadence === 'second' ? SECOND_MS - date.getMilliseconds() : (MINUTE_SECONDS - date.getSeconds()) * SECOND_MS - date.getMilliseconds();
    return Math.max(MIN_CLOCK_DELAY_MS, millisecondDelay);
};

class ClockTicker {
    readonly #timers: ClockTickerTimers;
    readonly #getCadence: () => ClockTickCadence | null;
    readonly #onTick: () => void;
    #generation = 0;
    #timerId: number | null = null;

    constructor(options: ClockTickerOptions) {
        this.#timers = options.timers;
        this.#getCadence = options.getCadence;
        this.#onTick = options.onTick;
    }

    start(): void {
        if (this.#timerId !== null) {
            return;
        }
        this.#generation += 1;
        this.#schedule(this.#generation);
    }

    restart(): void {
        this.stop();
        this.start();
    }

    stop(): void {
        this.#generation += 1;
        this.#timers.clearTimer(this.#timerId);
        this.#timerId = null;
    }

    #schedule(generation: number): void {
        const cadence = this.#getCadence();
        if (cadence === null) {
            return;
        }
        const timerId = this.#timers.setTimer(
            (): void => {
                if (generation !== this.#generation) {
                    return;
                }
                this.#timerId = null;
                this.#onTick();
                if (generation !== this.#generation) {
                    return;
                }
                this.#schedule(generation);
            },
            resolveClockTickDelayMs(new Date(), cadence)
        );
        if (timerId === null) {
            throw new Error('ClockTicker failed to allocate a timer');
        }
        this.#timerId = timerId;
    }
}

export { ClockTicker, resolveClockTickDelayMs };
export type { ClockTickCadence, ClockTickerOptions, ClockTickerTimers };

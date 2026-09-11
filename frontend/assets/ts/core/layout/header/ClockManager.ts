/* SoAI - Shared layout clock manager [frontend/assets/ts/core/layout/header/ClockManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { readStorageJson, removeStorageKey, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { ClockTicker, type ClockTickCadence } from '@core/time/clockTicker.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import type { ClockDisplayMode, ClockFormat } from '@core/layout/header/state.ts';

export interface ClockManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getDomMany: (keys: string[]) => (HTMLElement | null)[];
    getClockFormat: () => ClockFormat;
    getHeaderClockEnabled: () => boolean;
    getClockSecondsEnabled: () => boolean;
    clearTimer: (id: number | null) => void;
    setTimer: (callback: () => void, delay: number, options?: { repeat?: boolean }) => number | null;
    updateText: (element: Element, text: string) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
}

interface ClockManagerOptions {
    header: ClockManagerHost;
}

const CLOCK_DISPLAY_MODE_STORAGE_KEY = 'soai.header.clock.displayMode';

const isClockDisplayMode = (value: JsonValue | null | undefined): value is ClockDisplayMode => value === 'digital' || value === 'analog';

const resolveHTMLElement = (element: Element | null): HTMLElement | null => (element instanceof HTMLElement ? element : null);

export class ClockManager {
    header: ClockManagerHost;
    ticker: ClockTicker;
    format: ClockFormat = '24h';
    displayMode: ClockDisplayMode = 'digital';
    headerClockEnabled = true;
    clockSecondsEnabled = false;
    timeNode: HTMLElement | null = null;
    dateNode: HTMLElement | null = null;
    button: HTMLElement | null = null;
    clockNode: HTMLElement | null = null;
    hourHand: HTMLElement | null = null;
    minuteHand: HTMLElement | null = null;
    secondHand: HTMLElement | null = null;

    constructor({ header }: ClockManagerOptions) {
        this.header = header;
        if (!this.header || !isFunction(this.header.on)) {
            throw new Error('ClockManager requires a header with event binding support');
        }
        this.ticker = new ClockTicker({
            timers: {
                setTimer: (callback, delay, options) => this.header.setTimer(callback, delay, options),
                clearTimer: (id) => this.header.clearTimer(id)
            },
            getCadence: () => this.#getTickCadence(),
            onTick: () => this.updateClock()
        });
        this.format = '24h';
        this.displayMode = 'digital';
        this.headerClockEnabled = true;
        this.clockSecondsEnabled = false;
        this.timeNode = null;
        this.dateNode = null;
        this.button = null;
        this.clockNode = null;
        this.hourHand = null;
        this.minuteHand = null;
        this.secondHand = null;
    }

    #requireDom(): { timeNode: HTMLElement; dateNode: HTMLElement; button: HTMLElement; clockNode: HTMLElement; hourHand: HTMLElement; minuteHand: HTMLElement; secondHand: HTMLElement } {
        const timeNode = this.timeNode;
        const dateNode = this.dateNode;
        const button = this.button;
        const clockNode = this.clockNode;
        const hourHand = this.hourHand;
        const minuteHand = this.minuteHand;
        const secondHand = this.secondHand;
        if (!timeNode || !dateNode || !button || !clockNode || !hourHand || !minuteHand || !secondHand) {
            throw new Error('ClockManager is not initialized');
        }
        return { timeNode, dateNode, button, clockNode, hourHand, minuteHand, secondHand };
    }

    #readDisplayMode(): ClockDisplayMode {
        let stored: JsonValue | null | undefined;
        try {
            stored = readStorageJson('localStorage', CLOCK_DISPLAY_MODE_STORAGE_KEY);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('ClockManager', 'Removed invalid clock display mode preference', { message: runtimeError.message });
            removeStorageKey('localStorage', CLOCK_DISPLAY_MODE_STORAGE_KEY);
            return 'digital';
        }
        return isClockDisplayMode(stored) ? stored : 'digital';
    }

    #setDisplayMode(mode: ClockDisplayMode): void {
        this.displayMode = mode;
        writeStorageJson('localStorage', CLOCK_DISPLAY_MODE_STORAGE_KEY, mode);
        this.#applyDisplayMode();
    }

    #applyDisplayMode(): void {
        const { button, clockNode } = this.#requireDom();
        const analog = this.displayMode === 'analog';
        button.classList.toggle('clock-button--analog', analog);
        button.classList.toggle('clock-button--digital', !analog);
        clockNode.classList.toggle('header-clock--analog', analog);
        clockNode.classList.toggle('header-clock--digital', !analog);
        this.header.updateAttribute(button, 'aria-pressed', analog ? 'true' : 'false');
    }

    #syncPreferenceState(): void {
        this.headerClockEnabled = this.header.getHeaderClockEnabled();
        this.clockSecondsEnabled = this.headerClockEnabled && this.header.getClockSecondsEnabled();
    }

    #getTickCadence(): ClockTickCadence | null {
        if (!this.headerClockEnabled) {
            return null;
        }
        return this.clockSecondsEnabled ? 'second' : 'minute';
    }

    #applyVisibility(): void {
        const { button, clockNode, secondHand } = this.#requireDom();
        setVisibilityState(button, this.headerClockEnabled, { ariaHidden: true });
        if (this.headerClockEnabled) {
            button.removeAttribute('tabindex');
        } else {
            button.setAttribute('tabindex', '-1');
        }
        clockNode.classList.toggle('header-clock--seconds-disabled', !this.clockSecondsEnabled);
        secondHand.hidden = !this.clockSecondsEnabled;
    }

    async initialize(): Promise<void> {
        const [timeNode, dateNode, button] = this.header.getDomMany(['clockTime', 'clockDate', 'clockButton']);
        this.timeNode = timeNode ?? null;
        this.dateNode = dateNode ?? null;
        this.button = button ?? null;
        this.clockNode = this.button ? resolveHTMLElement(dom.resolve('.header-clock', this.button)) : null;
        this.hourHand = this.button ? resolveHTMLElement(dom.resolve('.clock-hand--hour', this.button)) : null;
        this.minuteHand = this.button ? resolveHTMLElement(dom.resolve('.clock-hand--minute', this.button)) : null;
        this.secondHand = this.button ? resolveHTMLElement(dom.resolve('.clock-hand--second', this.button)) : null;
        if (!(this.timeNode && this.dateNode && this.button && this.clockNode && this.hourHand && this.minuteHand && this.secondHand)) {
            throw new Error('ClockManager requires digital and analog clock elements');
        }
        this.format = this.header.getClockFormat();
        this.#syncPreferenceState();
        this.displayMode = this.#readDisplayMode();
        this.#applyDisplayMode();
        this.#applyVisibility();
        if (this.headerClockEnabled) {
            this.updateClock();
        }
        this.ticker.restart();
        this.header.on(this.button, 'click', (event: Event) => this.handleButtonClick(event));
        this.updateButtonLabels();
    }

    destroy(): void {
        this.ticker.stop();
        this.timeNode = null;
        this.dateNode = null;
        this.button = null;
        this.clockNode = null;
        this.hourHand = null;
        this.minuteHand = null;
        this.secondHand = null;
    }

    localize(): void {
        this.updateButtonLabels();
    }

    refresh(): void {
        this.format = this.header.getClockFormat();
        this.#syncPreferenceState();
        this.#applyVisibility();
        if (this.headerClockEnabled) {
            this.updateClock();
        }
        this.ticker.restart();
    }

    handleButtonClick(event: Event): void {
        event.preventDefault();
        event.stopPropagation();
        if (!this.headerClockEnabled) {
            return;
        }
        this.#setDisplayMode(this.displayMode === 'digital' ? 'analog' : 'digital');
        this.updateClock();
    }

    private updateClock(): void {
        if (!this.headerClockEnabled) {
            return;
        }
        const { timeNode, dateNode, hourHand, minuteHand, secondHand } = this.#requireDom();
        const now = new Date();
        const timeOptions: Intl.DateTimeFormatOptions = this.clockSecondsEnabled ? { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: this.format === '12h' } : { hour: '2-digit', minute: '2-digit', hour12: this.format === '12h' };
        const dateOptions: Intl.DateTimeFormatOptions = { year: 'numeric', month: 'short', day: 'numeric' };
        this.header.updateText(timeNode, i18n.formatDate(now, timeOptions));
        this.header.updateText(dateNode, i18n.formatDate(now, dateOptions));
        const seconds = this.clockSecondsEnabled ? now.getSeconds() : 0;
        const minutes = now.getMinutes();
        const hours = now.getHours() % 12;
        hourHand.style.setProperty('--clock-hand-angle', `${(hours + minutes / 60) * 30}deg`);
        minuteHand.style.setProperty('--clock-hand-angle', `${(minutes + seconds / 60) * 6}deg`);
        if (this.clockSecondsEnabled) {
            secondHand.style.setProperty('--clock-hand-angle', `${seconds * 6}deg`);
        }
    }

    updateButtonLabels(): void {
        const { button } = this.#requireDom();
        const label = i18n.t('header.actions.toggleClockFormat');
        this.header.updateAttribute(button, 'aria-label', label);
        setTooltipText(button, label);
    }
}

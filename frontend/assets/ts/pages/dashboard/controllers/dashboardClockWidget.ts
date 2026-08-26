/* SoAI - Dashboard page clock widget [frontend/assets/ts/pages/dashboard/controllers/dashboardClockWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { transitionContentElements } from '@core/animations/contentFadeTransition.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { i18n } from '@core/i18n/index.ts';
import { getResolvedLocalizationLocale } from '@core/localization/public.ts';
import { CLOCK_PREFERENCES_CHANGED_EVENT } from '@core/storage/clockPreferences.ts';
import { ClockTicker, type ClockTickCadence } from '@core/time/clockTicker.ts';
import { buildWeekDays, resolveWeekStartsOnSunday } from '@core/time/localCalendar.ts';
import { resolveBrowserTimezone } from '@core/timezones/timezones.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { DASHBOARD_ACTION_CLOCK_MODE_CYCLE } from '@pages/dashboard/actions.ts';
import { DashboardClockDigitalDisplayWidget } from '@pages/dashboard/controllers/dashboardClockDigitalDisplayWidget.ts';
import { CLOCK_DATE_OPTIONS, CLOCK_DEGREES_PER_HOUR, CLOCK_DEGREES_PER_MINUTE, CLOCK_DEGREES_PER_SECOND, CLOCK_MAJOR_TICK_EVERY, CLOCK_TICK_COUNT, CLOCK_WEEK_DAYS, CLOCK_WEEKDAY_OPTIONS, buildDashboardClockClassName, formatDayOfYearCounter, formatModifiedJulianDate, formatSwatchInternetTime, formatTimeZoneOffset, nextClockDisplayMode, resolveClockTimeOptions, type DashboardClockDisplayMode } from '@pages/dashboard/controllers/dashboardClockTimeWidget.ts';
import type { DashboardHost, DashboardTimerControl } from '@core/edition/dashboardContribution.ts';

interface DashboardClockControllerDependencies {
    host: DashboardHost;
    timers: DashboardTimerControl;
    on: (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;
    getClockSecondsEnabled: () => boolean;
    isDestroyed: () => boolean;
}

class DashboardClockController {
    readonly #host: DashboardHost;
    readonly #digitalDisplay: DashboardClockDigitalDisplayWidget;
    readonly #disposers: Array<() => void>;
    readonly #getClockSecondsEnabled: () => boolean;
    readonly #isDestroyed: () => boolean;
    readonly #ticker: ClockTicker;
    readonly #handleLocalizationChanged = (): void => {
        if (this.#isDestroyed()) {
            return;
        }
        this.#lastWeekDayKey = null;
        this.#updateDisplay();
    };
    readonly #handleClockPreferencesChanged = (): void => {
        if (this.#isDestroyed() || !this.#syncClockPreferenceState()) {
            return;
        }
        this.#applyClockClassName();
        if (this.#rendered) {
            this.#updateDisplay();
            this.#ticker.restart();
        }
    };
    #lastWeekDayKey: string | null = null;
    #mode: DashboardClockDisplayMode = 'analog';
    #clockSecondsEnabled = false;
    #rendered = false;

    constructor(dependencies: DashboardClockControllerDependencies) {
        this.#host = dependencies.host;
        this.#digitalDisplay = new DashboardClockDigitalDisplayWidget({ host: dependencies.host, timers: dependencies.timers, isDestroyed: dependencies.isDestroyed });
        this.#getClockSecondsEnabled = dependencies.getClockSecondsEnabled;
        this.#isDestroyed = dependencies.isDestroyed;
        this.#clockSecondsEnabled = this.#getClockSecondsEnabled();
        this.#ticker = new ClockTicker({
            timers: {
                setTimer: (callback, delay, options) => dependencies.timers.setTimer(callback, delay, options),
                clearTimer: (id) => dependencies.timers.clearTimer(id)
            },
            getCadence: (): ClockTickCadence => (this.#clockSecondsEnabled ? 'second' : 'minute'),
            onTick: (): void => this.#updateDisplay()
        });
        this.#disposers = [dependencies.on(getWindow(), 'soai:localization:changed', this.#handleLocalizationChanged), dependencies.on(getWindow(), CLOCK_PREFERENCES_CHANGED_EVENT, this.#handleClockPreferencesChanged)];
    }

    renderSection(): void {
        if (this.#isDestroyed()) {
            return;
        }
        this.#rendered = true;
        this.#syncClockPreferenceState();
        this.#renderMarkup();
        this.#ticker.restart();
    }

    destroy(): void {
        this.#rendered = false;
        this.#ticker.stop();
        this.#digitalDisplay.clearPendingAnimations();
        this.#lastWeekDayKey = null;
        for (const dispose of this.#disposers) {
            dispose();
        }
    }

    cycleMode(): void {
        if (this.#isDestroyed()) {
            return;
        }
        this.#mode = nextClockDisplayMode(this.#mode);
        this.#renderClockFace();
    }

    #renderMarkup(): void {
        const content = narrowHTMLElement(this.#host.requireUI('clock-content'), 'dashboard clock content');
        this.#digitalDisplay.clearPendingAnimations();
        this.#host.replaceElementContent(content, this.#buildMarkup(), { escape: false });
        this.#host.flushDOMUpdates();
        this.#lastWeekDayKey = null;
        this.#updateDisplay();
    }

    #renderClockFace(): void {
        const content = narrowHTMLElement(this.#host.requireUI('clock-content'), 'dashboard clock content');
        const wrapper = this.#host.optionalHTMLElement('.dashboard-clock', content);
        const shell = this.#host.optionalHTMLElement('.dashboard-clock-shell', content);
        if (!wrapper || !shell) {
            this.#renderMarkup();
            return;
        }
        this.#digitalDisplay.clearPendingAnimations();
        transitionContentElements({
            elements: [shell],
            render: (): void => {
                wrapper.className = this.#clockClassName();
                this.#host.replaceElementContent(shell, this.#mode === 'analog' ? this.#buildAnalogFace() : this.#buildDigitalFace(), { escape: false });
                this.#host.flushDOMUpdates();
                this.#updateDisplay();
            }
        });
    }

    #buildMarkup(): HTMLElement {
        const wrapper = narrowHTMLElement(this.#host.createElement('div', { className: this.#clockClassName() }), 'dashboard clock wrapper');
        const meta = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-meta' }), 'dashboard clock meta');
        const timeColumn = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-time-column' }), 'dashboard clock time column');
        const digital = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-digital', dataset: { clockTime: 'true' } }), 'dashboard clock digital');
        const swatch = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-swatch', dataset: { clockSwatch: 'true' } }), 'dashboard clock swatch internet time');
        setTooltipText(swatch, i18n.t('dashboard.sections.clock.internetTime'));
        timeColumn.append(digital, swatch);
        const dayColumn = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-day-column' }), 'dashboard clock day column');
        const dayOfYear = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-day-of-year', dataset: { clockDayOfYear: 'true' } }), 'dashboard clock day of year');
        const modifiedJulianDate = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-mjd', dataset: { clockMjd: 'true' } }), 'dashboard clock modified julian date');
        setTooltipText(modifiedJulianDate, i18n.t('dashboard.sections.clock.modifiedJulianDate'));
        dayColumn.append(dayOfYear, modifiedJulianDate);
        meta.append(timeColumn, dayColumn);
        const shell = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-shell' }), 'dashboard clock shell');
        shell.appendChild(this.#mode === 'analog' ? this.#buildAnalogFace() : this.#buildDigitalFace());
        const date = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-date', dataset: { clockDate: 'true' } }), 'dashboard clock date');
        wrapper.append(meta, shell, date, this.#buildWeek(), this.#buildTimeZone());
        return wrapper;
    }

    #buildAnalogFace(): HTMLElement {
        const face = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-face', dataset: { clockFace: 'true' }, 'data-action': DASHBOARD_ACTION_CLOCK_MODE_CYCLE }), 'dashboard clock face');
        face.appendChild(this.#buildTicks());
        face.append(this.#buildHand('hour'), this.#buildHand('minute'), this.#buildHand('second'));
        face.appendChild(narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-cap' }), 'dashboard clock cap'));
        return face;
    }

    #buildDigitalFace(): HTMLElement {
        return this.#digitalDisplay.buildFace(DASHBOARD_ACTION_CLOCK_MODE_CYCLE);
    }

    #buildWeek(): HTMLElement {
        const week = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-week', dataset: { clockWeek: 'true' } }), 'dashboard clock week');
        for (let index = 0; index < CLOCK_WEEK_DAYS; index += 1) {
            const day = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-week-day', dataset: { clockWeekDay: String(index) } }), 'dashboard clock week day');
            day.appendChild(narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-week-dow', dataset: { clockWeekDow: 'true' } }), 'dashboard clock week dow'));
            day.appendChild(narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-week-date', dataset: { clockWeekDate: 'true' } }), 'dashboard clock week date'));
            week.appendChild(day);
        }
        return week;
    }

    #buildTimeZone(): HTMLElement {
        const card = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-timezone dashboard-throughput-active' }), 'dashboard clock time zone');
        card.append(narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-active-label dashboard-clock-timezone-name', dataset: { clockTimeZoneName: 'true' } }, i18n.t('automation.modal.fields.timezone')), 'dashboard clock time zone name'), narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-active-value dashboard-clock-timezone-offset', dataset: { clockTimeZoneOffset: 'true' } }), 'dashboard clock time zone offset'));
        return card;
    }

    #buildTicks(): HTMLElement {
        const ticks = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-ticks', 'data-action': DASHBOARD_ACTION_CLOCK_MODE_CYCLE }), 'dashboard clock ticks');
        for (let index = 0; index < CLOCK_TICK_COUNT; index += 1) {
            const isMajor = index % CLOCK_MAJOR_TICK_EVERY === 0;
            const tick = narrowHTMLElement(this.#host.createElement('div', { className: isMajor ? 'dashboard-clock-tick dashboard-clock-tick-major' : 'dashboard-clock-tick' }), 'dashboard clock tick');
            tick.style.setProperty('--dashboard-clock-tick-angle', `${index * CLOCK_DEGREES_PER_HOUR}deg`);
            ticks.appendChild(tick);
        }
        return ticks;
    }

    #buildHand(kind: 'hour' | 'minute' | 'second'): HTMLElement {
        return narrowHTMLElement(this.#host.createElement('div', { className: `dashboard-clock-hand dashboard-clock-hand-${kind}`, dataset: { clockHand: kind } }), `dashboard clock ${kind} hand`);
    }

    #syncClockPreferenceState(): boolean {
        const clockSecondsEnabled = this.#getClockSecondsEnabled();
        const changed = this.#clockSecondsEnabled !== clockSecondsEnabled;
        this.#clockSecondsEnabled = clockSecondsEnabled;
        return changed;
    }

    #clockClassName(): string {
        return buildDashboardClockClassName(this.#mode, this.#clockSecondsEnabled);
    }

    #applyClockClassName(): void {
        const content = this.#host.optionalUI('clock-content');
        const wrapper = content ? this.#host.optionalHTMLElement('.dashboard-clock', content) : null;
        if (wrapper) {
            wrapper.className = this.#clockClassName();
        }
    }

    #updateDisplay(): void {
        if (this.#isDestroyed()) {
            return;
        }
        const content = this.#host.optionalUI('clock-content');
        if (!content) {
            return;
        }
        const now = new Date();
        const face = this.#host.optionalHTMLElement('[data-clock-face]', content);
        const timeNode = this.#host.optionalHTMLElement('[data-clock-time]', content);
        const swatchNode = this.#host.optionalHTMLElement('[data-clock-swatch]', content);
        const dayOfYearNode = this.#host.optionalHTMLElement('[data-clock-day-of-year]', content);
        const modifiedJulianDateNode = this.#host.optionalHTMLElement('[data-clock-mjd]', content);
        const dateNode = this.#host.optionalHTMLElement('[data-clock-date]', content);
        const timeZoneNameNode = this.#host.optionalHTMLElement('[data-clock-time-zone-name]', content);
        const timeZoneOffsetNode = this.#host.optionalHTMLElement('[data-clock-time-zone-offset]', content);
        if (face) {
            const seconds = this.#clockSecondsEnabled ? now.getSeconds() : 0;
            const minutes = now.getMinutes();
            const hours = now.getHours() % 12;
            face.style.setProperty('--dashboard-clock-minute-angle', `${(minutes + seconds / 60) * CLOCK_DEGREES_PER_MINUTE}deg`);
            face.style.setProperty('--dashboard-clock-hour-angle', `${(hours + minutes / 60) * CLOCK_DEGREES_PER_HOUR}deg`);
            if (this.#clockSecondsEnabled) {
                face.style.setProperty('--dashboard-clock-second-angle', `${seconds * CLOCK_DEGREES_PER_SECOND}deg`);
            }
        }
        if (timeNode) {
            applyTextContent(timeNode, i18n.formatDate(now, resolveClockTimeOptions(this.#clockSecondsEnabled)));
        }
        if (swatchNode) {
            applyTextContent(swatchNode, formatSwatchInternetTime(now));
        }
        if (dayOfYearNode) {
            applyTextContent(dayOfYearNode, formatDayOfYearCounter(now));
        }
        if (modifiedJulianDateNode) {
            applyTextContent(modifiedJulianDateNode, formatModifiedJulianDate(now));
        }
        this.#digitalDisplay.update(content, now);
        if (dateNode) {
            applyTextContent(dateNode, i18n.formatDate(now, CLOCK_DATE_OPTIONS));
        }
        if (timeZoneNameNode) {
            applyTextContent(timeZoneNameNode, resolveBrowserTimezone());
        }
        if (timeZoneOffsetNode) {
            applyTextContent(timeZoneOffsetNode, formatTimeZoneOffset(now));
        }
        const dayKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
        if (dayKey !== this.#lastWeekDayKey) {
            this.#lastWeekDayKey = dayKey;
            this.#fillWeek(now, content);
        }
    }

    #fillWeek(now: Date, content: Element): void {
        const weekDays = buildWeekDays(now, resolveWeekStartsOnSunday(getResolvedLocalizationLocale()));
        for (let index = 0; index < CLOCK_WEEK_DAYS; index += 1) {
            const date = weekDays[index];
            if (!(date instanceof Date)) {
                throw new Error('Dashboard clock week days must resolve to seven dates');
            }
            const cell = this.#host.optionalHTMLElement(`[data-clock-week-day='${index}']`, content);
            if (!cell) {
                continue;
            }
            const dow = this.#host.optionalHTMLElement('[data-clock-week-dow]', cell);
            const dayNumber = this.#host.optionalHTMLElement('[data-clock-week-date]', cell);
            if (dow) {
                applyTextContent(dow, i18n.formatDate(date, CLOCK_WEEKDAY_OPTIONS));
            }
            if (dayNumber) {
                applyTextContent(dayNumber, i18n.formatNumber(date.getDate()));
            }
            cell.classList.toggle('dashboard-clock-week-day-active', date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate());
        }
    }
}

export { DashboardClockController };
export type { DashboardClockControllerDependencies };

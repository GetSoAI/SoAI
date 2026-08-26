/* SoAI - Automation page month layout controller [frontend/assets/ts/pages/automation/controllers/AutomationMonthLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { parseFirstPositiveCssPixelValue, parsePositiveCssPixelValue } from '@core/dom/attributes.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { optionalAutomationMonthDay, optionalAutomationMonthDayHeader, optionalAutomationMonthZones, optionalAutomationZoneChip } from '@pages/automation/dom.ts';
import type { AutomationViewMode } from '@pages/automation/types.ts';

interface MonthLayoutControllerDependencies {
    root: HTMLElement;
    calendarRoot: HTMLElement;
    requestAnimationFrame: (callback: () => void) => number;
    getViewMode: () => AutomationViewMode;
    applyMaxChipsPerDay: (value: number) => void;
    queueRender: () => void;
}

class AutomationMonthLayoutController {
    readonly #dependencies: MonthLayoutControllerDependencies;
    #resizeObserver: ResizeObserver | null = null;
    #queued = false;
    #connected = false;
    #maxChipsPerDay: number | null = null;
    readonly #onAbort = (): void => {
        this.destroy();
    };

    constructor(dependencies: MonthLayoutControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        this.#connected = true;
        this.#resizeObserver = new ResizeObserver(() => this.#queueMeasureFromDom());
        this.#resizeObserver.observe(this.#dependencies.calendarRoot);
        this.#resizeObserver.observe(this.#dependencies.root);
        signal.addEventListener('abort', this.#onAbort, { once: true });
    }

    destroy(): void {
        this.#connected = false;
        this.#queued = false;
        this.#maxChipsPerDay = null;
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = null;
    }

    measureFromDom(): boolean {
        if (!this.#connected) {
            return false;
        }
        const viewMode = this.#dependencies.getViewMode();
        if (viewMode !== 'month') {
            return false;
        }

        const dayElement = optionalAutomationMonthDay(this.#dependencies.calendarRoot);
        if (!dayElement) {
            return false;
        }

        const rect = measureLayoutBox(dayElement);
        if (!(rect.width > 0 && rect.height > 0)) {
            return false;
        }

        const maxChipsPerDay = this.#resolveMonthMaxChipsPerDay(dayElement, rect.height);
        if (this.#maxChipsPerDay === maxChipsPerDay) {
            return false;
        }
        this.#maxChipsPerDay = maxChipsPerDay;
        this.#dependencies.applyMaxChipsPerDay(maxChipsPerDay);
        return true;
    }

    #queueMeasureFromDom(): void {
        if (!this.#connected || this.#queued) {
            return;
        }
        this.#queued = true;
        this.#dependencies.requestAnimationFrame(() => {
            if (!this.#connected) {
                this.#queued = false;
                return;
            }
            this.#queued = false;
            if (this.measureFromDom()) {
                this.#dependencies.queueRender();
            }
        });
    }

    #resolveMonthMaxChipsPerDay(dayElement: HTMLElement, dayHeightPx: number): number {
        const style = getComputedStyle(dayElement);
        const paddingTop = parsePositiveCssPixelValue(style.paddingTop, 0);
        const paddingBottom = parsePositiveCssPixelValue(style.paddingBottom, 0);
        const borderTop = parsePositiveCssPixelValue(style.borderTopWidth, 0);
        const borderBottom = parsePositiveCssPixelValue(style.borderBottomWidth, 0);
        const dayGapPx = parseFirstPositiveCssPixelValue(style.gap, parsePositiveCssPixelValue(style.rowGap, 0));

        const headerElement = optionalAutomationMonthDayHeader(dayElement);
        const headerHeightPx = headerElement ? measureLayoutBox(headerElement).height : 0;

        const zonesElement = optionalAutomationMonthZones(dayElement);
        const zonesGapPx = zonesElement ? parseFirstPositiveCssPixelValue(getComputedStyle(zonesElement).gap, 0) : 0;

        const chipElement = optionalAutomationZoneChip(this.#dependencies.calendarRoot);
        const measuredChipHeightPx = chipElement ? measureLayoutBox(chipElement).height : 0;
        const chipHeightPx = measuredChipHeightPx > 0 ? measuredChipHeightPx : 26;

        const SAFETY_PX = 2;
        const availablePx = dayHeightPx - borderTop - borderBottom - paddingTop - paddingBottom - headerHeightPx - dayGapPx - SAFETY_PX;
        if (!(availablePx > 0 && chipHeightPx > 0)) {
            return 0;
        }

        const raw = Math.floor((availablePx + zonesGapPx) / (chipHeightPx + zonesGapPx));
        return clampNumber(raw, 0, 4);
    }
}

export { AutomationMonthLayoutController };

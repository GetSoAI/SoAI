/* SoAI - Automation page time grid interaction controller [frontend/assets/ts/pages/automation/controllers/AutomationTimeGridInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { requireIsoDateToUtcMs } from '@core/time/localCalendar.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { AUTOMATION_ACTION_TIME_GRID_CREATE_AT } from '@features/automation/public.ts';
import { requireAutomationTimeGridCanvasInner, resolveAutomationWeekColumnCanvas } from '@pages/automation/dom.ts';
import type { AutomationUiRefs } from '@pages/automation/types.ts';

interface InteractionDependencies {
    ui: AutomationUiRefs;
    openCreateModalAt: (scheduledAtUtcMs: number) => void;
    hourHeightPx: number;
}

const resolveMinutesFromPointer = (canvasInner: HTMLElement, clientY: number, hourHeightPx: number): number => {
    const rect = measureLayoutBox(canvasInner);
    const yCoordinate = clientY - rect.top;
    const minutes = (yCoordinate / hourHeightPx) * 60;
    return clampNumber(minutes, 0, 24 * 60 - 1);
};

const snapshotMinutes = (minutes: number, snapshot: number): number => {
    const snapped = Math.round(minutes / snapshot) * snapshot;
    return clampNumber(snapped, 0, 24 * 60 - snapshot);
};

const isTimeGridCreateAction = (value: string | undefined): value is typeof AUTOMATION_ACTION_TIME_GRID_CREATE_AT => value === AUTOMATION_ACTION_TIME_GRID_CREATE_AT;

class AutomationTimeGridInteractionController {
    readonly #dependencies: InteractionDependencies;
    #hoverCanvas: HTMLElement | null = null;
    #hoverTopPx: number | null = null;

    constructor(dependencies: InteractionDependencies) {
        if (!isFiniteNumber(dependencies.hourHeightPx) || dependencies.hourHeightPx <= 0) {
            throw new Error('Automation time grid hour height must be a positive finite number');
        }
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        bindDataActionListener({
            root: this.#dependencies.ui.calendarRoot,
            eventType: 'click',
            signal,
            isAction: isTimeGridCreateAction,
            preventDefault: 'never',
            onAction: ({ event, actionElement }): void => this.onCalendarCreateClick(event, actionElement)
        });
        bindDataActionListener({
            root: this.#dependencies.ui.calendarRoot,
            eventType: 'keydown',
            signal,
            isAction: isTimeGridCreateAction,
            preventDefault: 'never',
            onAction: ({ event, actionElement }): void => this.onCalendarCreateKeydown(event, actionElement)
        });
        const handlePointerMove = (event: PointerEvent): void => this.onPointerHover(event);
        this.#dependencies.ui.calendarRoot.addEventListener('pointermove', handlePointerMove, { signal });
        const handlePointerLeave = (): void => this.clearHover();
        this.#dependencies.ui.calendarRoot.addEventListener('pointerleave', handlePointerLeave, { signal });
    }

    destroy(): void {
        this.clearHover();
    }

    onCalendarCreateClick(event: Event, actionElement: HTMLElement): void {
        if (!(event instanceof MouseEvent)) {
            return;
        }
        if (actionElement.dataset['automationDayCanvas'] === 'true') {
            const iso = actionElement.dataset['date'] ?? '';
            this.#openCreateAtCanvasPoint(actionElement, iso, measureLayoutPoint(event, actionElement).y);
            return;
        }
        if (actionElement.dataset['automationWeekColumn'] === 'true') {
            const iso = actionElement.dataset['date'] ?? '';
            const canvas = resolveAutomationWeekColumnCanvas(actionElement);
            this.#openCreateAtCanvasPoint(canvas, iso, measureLayoutPoint(event, canvas).y);
        }
    }

    onCalendarCreateKeydown(event: Event, actionElement: HTMLElement): void {
        if (!(event instanceof KeyboardEvent)) return;
        const currentMinutes = Number(actionElement.dataset['keyboardMinutes'] ?? 540);
        const keyAdjustments: Readonly<Record<string, number>> = { ArrowUp: -15, ArrowDown: 15, PageUp: -60, PageDown: 60 };
        const adjustment = keyAdjustments[event.key];
        if (adjustment !== undefined || event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            const nextMinutes = event.key === 'Home' ? 0 : event.key === 'End' ? 24 * 60 - 15 : clampNumber(currentMinutes + (adjustment ?? 0), 0, 24 * 60 - 15);
            actionElement.dataset['keyboardMinutes'] = String(nextMinutes);
            const canvas = actionElement.dataset['automationWeekColumn'] === 'true' ? resolveAutomationWeekColumnCanvas(actionElement) : actionElement;
            const canvasInner = requireAutomationTimeGridCanvasInner(canvas);
            canvasInner.style.setProperty('--automation-hover-top', `${(nextMinutes / 60) * this.#dependencies.hourHeightPx}px`);
            canvasInner.classList.add('is-hovering');
            return;
        }
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        const isoDate = actionElement.dataset['date'] ?? '';
        this.#openCreateAtMinutes(isoDate, clampNumber(currentMinutes, 0, 24 * 60 - 15));
    }

    #openCreateAtCanvasPoint(canvas: HTMLElement, isoDate: string, clientY: number): void {
        const startUtcMs = requireIsoDateToUtcMs(isoDate, 'Automation time grid date');
        const minutes = resolveMinutesFromPointer(requireAutomationTimeGridCanvasInner(canvas), clientY, this.#dependencies.hourHeightPx);
        const snappedMinutes = snapshotMinutes(minutes, 15);
        this.#openCreateAtMinutes(isoDate, snappedMinutes, startUtcMs);
    }

    #openCreateAtMinutes(isoDate: string, minutes: number, startUtcMs = requireIsoDateToUtcMs(isoDate, 'Automation time grid date')): void {
        const date = new Date(startUtcMs);
        date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
        this.#dependencies.openCreateModalAt(date.getTime());
    }

    onPointerHover(event: PointerEvent): void {
        if (event.pointerType && event.pointerType !== 'mouse') {
            return;
        }
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        if (target.closest('.automation-zone-block')) {
            this.clearHover();
            return;
        }
        const canvas = target.closest('.automation-time-grid-canvas');
        if (!(canvas instanceof HTMLElement)) {
            this.clearHover();
            return;
        }

        const inner = requireAutomationTimeGridCanvasInner(canvas);
        const minutes = resolveMinutesFromPointer(inner, measureLayoutPoint(event, inner).y, this.#dependencies.hourHeightPx);
        const hourIndex = Math.floor(minutes / 60);
        const topPx = hourIndex * this.#dependencies.hourHeightPx;
        const atStart = hourIndex === 0;
        const atEnd = hourIndex === 23;

        if (this.#hoverCanvas !== inner) {
            this.clearHover();
            this.#hoverCanvas = inner;
            this.#hoverTopPx = null;
        }

        if (this.#hoverCanvas && this.#hoverTopPx !== topPx) {
            this.#hoverCanvas.style.setProperty('--automation-hover-top', `${topPx}px`);
            this.#hoverTopPx = topPx;
        }
        this.#hoverCanvas.classList.add('is-hovering');
        this.#hoverCanvas.classList.toggle('is-hovering-start', atStart);
        this.#hoverCanvas.classList.toggle('is-hovering-end', atEnd);
    }

    clearHover(): void {
        if (this.#hoverCanvas) {
            this.#hoverCanvas.classList.remove('is-hovering');
            this.#hoverCanvas.classList.remove('is-hovering-start');
            this.#hoverCanvas.classList.remove('is-hovering-end');
            this.#hoverCanvas.style.removeProperty('--automation-hover-top');
        }
        this.#hoverCanvas = null;
        this.#hoverTopPx = null;
    }
}

export { AutomationTimeGridInteractionController };

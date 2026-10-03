/* SoAI - Automation page time grid interaction controller [frontend/assets/ts/pages/automation/controllers/AutomationTimeGridInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { requireIsoDateToUtcMs } from '@core/time/localCalendar.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { AUTOMATION_ACTION_TIME_GRID_CREATE_AT } from '@features/automation/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { formatAutomationCreateAtLabel } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { requireAutomationTimeGridCanvasInner, resolveAutomationTimeGridCanvas } from '@pages/automation/dom.ts';
import type { AutomationCalendarTimeFormat, AutomationUiRefs } from '@pages/automation/types.ts';

interface InteractionDependencies {
    ui: AutomationUiRefs;
    openCreateModalAt: (scheduledAtUtcMs: number) => void;
    getTimeFormat: () => AutomationCalendarTimeFormat;
    hourHeightPx: number;
}

const DAY_LAST_SLOT_MINUTES = 24 * 60 - 15;
const KEYBOARD_MINUTE_ADJUSTMENTS: Readonly<Record<string, number>> = { ArrowUp: -15, ArrowDown: 15, PageUp: -60, PageDown: 60 };

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

const isKeyboardCreateButton = (element: Element | null): element is HTMLButtonElement => element instanceof HTMLButtonElement && element.dataset['automationKeyboardCreate'] === 'true';

const readKeyboardMinutes = (button: HTMLButtonElement): number => clampNumber(Number(button.dataset['keyboardMinutes'] ?? 540), 0, DAY_LAST_SLOT_MINUTES);

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
        const root = this.#dependencies.ui.calendarRoot;
        bindDataActionListener({ root, eventType: 'click', signal, isAction: isTimeGridCreateAction, preventDefault: 'never', onAction: ({ event, actionElement }): void => this.onCalendarCreateClick(event, actionElement) });
        bindDataActionListener({ root, eventType: 'keydown', signal, isAction: isTimeGridCreateAction, preventDefault: 'never', onAction: ({ event, actionElement }): void => this.onCalendarCreateKeydown(event, actionElement) });
        const handlePointerMove = (event: PointerEvent): void => this.onPointerHover(event);
        root.addEventListener('pointermove', handlePointerMove, { signal });
        const handlePointerLeave = (): void => this.clearHover();
        root.addEventListener('pointerleave', handlePointerLeave, { signal });
        const handleFocusIn = (event: FocusEvent): void => this.#onFocusIn(event);
        root.addEventListener('focusin', handleFocusIn, { signal });
        const handleFocusOut = (event: FocusEvent): void => this.#onFocusOut(event);
        root.addEventListener('focusout', handleFocusOut, { signal });
    }

    destroy(): void {
        this.clearHover();
    }

    onCalendarCreateClick(event: Event, actionElement: HTMLElement): void {
        if (isKeyboardCreateButton(actionElement)) {
            this.#openCreateAtMinutes(actionElement.dataset['date'] ?? '', readKeyboardMinutes(actionElement));
            return;
        }
        if (!(event instanceof MouseEvent)) {
            return;
        }
        if (actionElement.dataset['automationDayCanvas'] === 'true') {
            this.#openCreateAtCanvasPoint(actionElement, actionElement.dataset['date'] ?? '', measureLayoutPoint(event, actionElement).y);
            return;
        }
        if (actionElement.dataset['automationWeekColumn'] === 'true') {
            const canvas = resolveAutomationTimeGridCanvas(actionElement);
            this.#openCreateAtCanvasPoint(canvas, actionElement.dataset['date'] ?? '', measureLayoutPoint(event, canvas).y);
        }
    }

    onCalendarCreateKeydown(event: Event, actionElement: HTMLElement): void {
        if (!(event instanceof KeyboardEvent) || !isKeyboardCreateButton(actionElement)) return;
        const adjustment = KEYBOARD_MINUTE_ADJUSTMENTS[event.key];
        if (adjustment === undefined && event.key !== 'Home' && event.key !== 'End') return;
        event.preventDefault();
        const nextMinutes = event.key === 'Home' ? 0 : event.key === 'End' ? DAY_LAST_SLOT_MINUTES : clampNumber(readKeyboardMinutes(actionElement) + (adjustment ?? 0), 0, DAY_LAST_SLOT_MINUTES);
        actionElement.dataset['keyboardMinutes'] = String(nextMinutes);
        const label = formatAutomationCreateAtLabel(actionElement.dataset['date'] ?? '', nextMinutes, this.#dependencies.getTimeFormat());
        actionElement.setAttribute('aria-label', label);
        setTooltipText(actionElement, label);
        this.#showKeyboardSlot(actionElement);
    }

    #onFocusIn(event: FocusEvent): void {
        if (isKeyboardCreateButton(event.target instanceof Element ? event.target : null) && event.target instanceof HTMLButtonElement) {
            this.#showKeyboardSlot(event.target);
        }
    }

    #onFocusOut(event: FocusEvent): void {
        if (isKeyboardCreateButton(event.target instanceof Element ? event.target : null)) {
            this.clearHover();
        }
    }

    #showKeyboardSlot(button: HTMLButtonElement): void {
        const container = button.parentElement;
        if (!container) return;
        const canvasInner = requireAutomationTimeGridCanvasInner(resolveAutomationTimeGridCanvas(container));
        if (this.#hoverCanvas !== canvasInner) {
            this.clearHover();
            this.#hoverCanvas = canvasInner;
        }
        this.#hoverTopPx = (readKeyboardMinutes(button) / 60) * this.#dependencies.hourHeightPx;
        canvasInner.style.setProperty('--automation-hover-top', `${this.#hoverTopPx}px`);
        canvasInner.classList.add('is-hovering', 'is-keyboard-slot');
    }

    #openCreateAtCanvasPoint(canvas: HTMLElement, isoDate: string, clientY: number): void {
        const startUtcMs = requireIsoDateToUtcMs(isoDate, 'Automation time grid date');
        const minutes = resolveMinutesFromPointer(requireAutomationTimeGridCanvasInner(canvas), clientY, this.#dependencies.hourHeightPx);
        this.#openCreateAtMinutes(isoDate, snapshotMinutes(minutes, 15), startUtcMs);
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

        if (this.#hoverCanvas !== inner) {
            this.clearHover();
            this.#hoverCanvas = inner;
            this.#hoverTopPx = null;
        }

        if (this.#hoverTopPx !== topPx) {
            inner.style.setProperty('--automation-hover-top', `${topPx}px`);
            this.#hoverTopPx = topPx;
        }
        inner.classList.remove('is-keyboard-slot');
        inner.classList.add('is-hovering');
        inner.classList.toggle('is-hovering-start', hourIndex === 0);
        inner.classList.toggle('is-hovering-end', hourIndex === 23);
    }

    clearHover(): void {
        if (this.#hoverCanvas) {
            this.#hoverCanvas.classList.remove('is-hovering', 'is-hovering-start', 'is-hovering-end', 'is-keyboard-slot');
            this.#hoverCanvas.style.removeProperty('--automation-hover-top');
        }
        this.#hoverCanvas = null;
        this.#hoverTopPx = null;
    }
}

export { AutomationTimeGridInteractionController };

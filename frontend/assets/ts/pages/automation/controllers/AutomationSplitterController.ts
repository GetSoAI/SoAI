/* SoAI - Automation page splitter controller [frontend/assets/ts/pages/automation/controllers/AutomationSplitterController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { inlineDelta } from '@core/layout/direction.ts';
import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { getWindow } from '@core/environment/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

interface SplitterControllerDependencies {
    root: HTMLElement;
    splitter: HTMLElement;
    minPercent: number;
    maxPercent: number;
    getInitialPercent: () => number;
    setPercent: (value: number) => void;
    commitPercent: (value: number) => void;
}

const KEYBOARD_STEP_PERCENT = 2;
const KEYBOARD_LARGE_STEP_PERCENT = 10;

class AutomationSplitterController {
    readonly #dependencies: SplitterControllerDependencies;
    #dragAbort: AbortController | null = null;

    constructor(dependencies: SplitterControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted) return;
        const splitter = this.#dependencies.splitter;
        splitter.setAttribute('aria-valuemin', String(this.#dependencies.minPercent));
        splitter.setAttribute('aria-valuemax', String(this.#dependencies.maxPercent));
        this.#syncValue(this.#dependencies.getInitialPercent());
        const handlePointerDown = (event: PointerEvent): void => this.onPointerDown(event);
        splitter.addEventListener('pointerdown', handlePointerDown, { signal });
        const handleKeyDown = (event: KeyboardEvent): void => this.onKeyDown(event);
        splitter.addEventListener('keydown', handleKeyDown, { signal });
        const handleAbort = (): void => this.destroy();
        signal.addEventListener('abort', handleAbort, { once: true });
    }

    destroy(): void {
        this.#dragAbort?.abort();
        this.#dragAbort = null;
    }

    onKeyDown(event: KeyboardEvent): void {
        if (this.#dragAbort !== null) {
            return;
        }
        const current = this.#dependencies.getInitialPercent();
        const step = event.shiftKey ? KEYBOARD_LARGE_STEP_PERCENT : KEYBOARD_STEP_PERCENT;
        const next = event.key === 'Home' ? this.#dependencies.minPercent : event.key === 'End' ? this.#dependencies.maxPercent : event.key === 'ArrowLeft' ? current + inlineDelta(-step, this.#dependencies.root) : event.key === 'ArrowRight' ? current + inlineDelta(step, this.#dependencies.root) : null;
        if (next === null) {
            return;
        }
        event.preventDefault();
        this.#apply(next, true);
    }

    onPointerDown(event: PointerEvent): void {
        if (event.button !== 0 || this.#dragAbort !== null) {
            return;
        }
        if (event.pointerType === 'mouse') {
            event.preventDefault();
        }
        this.#dragAbort = new AbortController();
        const { signal } = this.#dragAbort;

        const startPercent = this.#dependencies.getInitialPercent();
        const startX = measureLayoutPoint(event, this.#dependencies.root).x;
        this.#dependencies.splitter.classList.add('is-dragging');
        signal.addEventListener(
            'abort',
            () => {
                this.#dependencies.splitter.classList.remove('is-dragging');
                this.#apply(startPercent, false);
            },
            { once: true }
        );

        const handleMove = (moveEvent: PointerEvent): void => {
            if (moveEvent.pointerId !== event.pointerId) return;
            const width = measureLayoutBox(this.#dependencies.root).width;
            if (!isFiniteNumber(width) || width <= 0) {
                return;
            }
            const deltaX = measureLayoutPoint(moveEvent, this.#dependencies.root).x - startX;
            this.#apply(startPercent + (inlineDelta(deltaX, this.#dependencies.root) / width) * 100, false);
        };

        const handleUp = (endEvent: PointerEvent): void => {
            if (endEvent.pointerId !== event.pointerId) return;
            const next = this.#dependencies.getInitialPercent();
            this.destroy();
            if (endEvent.type === 'pointerup') {
                this.#apply(next, true);
            }
        };

        const windowRef = getWindow();
        windowRef.addEventListener('pointermove', handleMove, { signal });
        windowRef.addEventListener('pointerup', handleUp, { signal });
        windowRef.addEventListener('pointercancel', handleUp, { signal });
    }

    #apply(percent: number, commit: boolean): void {
        const next = clampNumber(percent, this.#dependencies.minPercent, this.#dependencies.maxPercent);
        this.#dependencies.setPercent(next);
        if (commit) {
            this.#dependencies.commitPercent(next);
        }
        this.#syncValue(next);
    }

    #syncValue(percent: number): void {
        this.#dependencies.splitter.setAttribute('aria-valuenow', String(Math.round(percent)));
    }
}

export { AutomationSplitterController };

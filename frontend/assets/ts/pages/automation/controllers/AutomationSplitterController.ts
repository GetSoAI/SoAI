/* SoAI - Automation page splitter controller [frontend/assets/ts/pages/automation/controllers/AutomationSplitterController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { getWindow } from '@core/environment/public.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

interface SplitterControllerDependencies {
    root: HTMLElement;
    splitter: HTMLElement;
    getInitialPercent: () => number;
    setPercent: (value: number) => void;
    commitPercent: (value: number) => void;
    clampPercent: (value: number) => number;
}

class AutomationSplitterController {
    readonly #dependencies: SplitterControllerDependencies;
    #dragAbort: AbortController | null = null;

    constructor(dependencies: SplitterControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        const handlePointerDown = (event: PointerEvent): void => this.onPointerDown(event);
        this.#dependencies.splitter.addEventListener('pointerdown', handlePointerDown, { signal });
    }

    destroy(): void {
        this.#dragAbort?.abort();
        this.#dragAbort = null;
    }

    onPointerDown(event: PointerEvent): void {
        if (event.button !== 0) {
            return;
        }
        if (event.pointerType === 'mouse') {
            event.preventDefault();
        }
        this.#dragAbort?.abort();
        this.#dragAbort = new AbortController();
        const { signal } = this.#dragAbort;

        const startPercent = this.#dependencies.getInitialPercent();
        const startX = measureLayoutPoint(event, this.#dependencies.root).x;
        this.#dependencies.splitter.classList.add('is-dragging');

        const handleMove = (moveEvent: PointerEvent): void => {
            const rect = measureLayoutBox(this.#dependencies.root);
            const width = rect.width;
            if (!isFiniteNumber(width) || width <= 0) {
                return;
            }
            const deltaX = measureLayoutPoint(moveEvent, this.#dependencies.root).x - startX;
            const deltaPercent = (deltaX / width) * 100;
            const next = this.#dependencies.clampPercent(startPercent + deltaPercent);
            this.#dependencies.setPercent(next);
        };

        const handleUp = (): void => {
            this.#dependencies.splitter.classList.remove('is-dragging');
            this.#dragAbort?.abort();
            this.#dragAbort = null;
            const next = this.#dependencies.clampPercent(this.#dependencies.getInitialPercent());
            this.#dependencies.commitPercent(next);
        };

        const windowRef = getWindow();
        windowRef.addEventListener('pointermove', handleMove, { signal });
        windowRef.addEventListener('pointerup', handleUp, { signal, once: true });
        windowRef.addEventListener('pointercancel', handleUp, { signal, once: true });
    }
}

export { AutomationSplitterController };

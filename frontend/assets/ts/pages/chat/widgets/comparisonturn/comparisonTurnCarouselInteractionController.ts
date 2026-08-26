/* SoAI - Wheel + swipe gestures for comparison-turn carousel navigation [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnCarouselInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComparisonNavDirection, ComparisonTurnSelectionController } from '@pages/chat/widgets/comparisonturn/comparisonTurnSelectionController.ts';
import { measureLayoutPoint } from '@core/layout/elementGeometry.ts';

type DragState = {
    pointerId: number;
    startX: number;
    startY: number;
    isDragging: boolean;
    lastX: number;
    lastY: number;
};

const canScrollHorizontally = (element: HTMLElement): boolean => {
    if (element.scrollWidth <= element.clientWidth + 1) {
        return false;
    }
    const overflowX = element.ownerDocument.defaultView?.getComputedStyle(element).overflowX ?? '';
    if (overflowX === 'auto') {
        return true;
    }
    if (overflowX === 'scroll') {
        return true;
    }
    if (overflowX === 'overlay') {
        return true;
    }
    return false;
};

const shouldIgnoreCarouselWheelEvent = (inputArguments: { viewport: HTMLElement; eventTarget: EventTarget | null }): boolean => {
    const target = inputArguments.eventTarget;
    if (!(target instanceof Element)) {
        return false;
    }
    let current: Element | null = target;
    while (current && current !== inputArguments.viewport) {
        if (current instanceof HTMLElement && canScrollHorizontally(current)) {
            return true;
        }
        current = current.parentElement;
    }
    return false;
};

class ComparisonTurnCarouselInteractionController {
    readonly #abortControllerByRoot = new Map<HTMLElement, AbortController>();
    readonly #wheelAccumulatorByRoot = new Map<HTMLElement, number>();
    readonly #dragStateByRoot = new Map<HTMLElement, DragState>();

    dispose(): void {
        for (const controller of this.#abortControllerByRoot.values()) {
            controller.abort();
        }
        this.#abortControllerByRoot.clear();
        this.#wheelAccumulatorByRoot.clear();
        this.#dragStateByRoot.clear();
    }

    pruneKnownRoots(knownRoots: ReadonlySet<HTMLElement>): void {
        for (const [root, controller] of this.#abortControllerByRoot.entries()) {
            if (!root.isConnected || !knownRoots.has(root)) {
                controller.abort();
                this.#abortControllerByRoot.delete(root);
                this.#wheelAccumulatorByRoot.delete(root);
                this.#dragStateByRoot.delete(root);
            }
        }
    }

    ensureMounted(inputArguments: { root: HTMLElement; viewport: HTMLElement; assistantTurnTimestamp: number; resolveSlideCount: () => number | null; selection: ComparisonTurnSelectionController; onSelectionChanged: () => void }): void {
        if (this.#abortControllerByRoot.has(inputArguments.root)) {
            return;
        }
        const abortController = new AbortController();
        const signal = abortController.signal;
        this.#abortControllerByRoot.set(inputArguments.root, abortController);

        inputArguments.viewport.addEventListener(
            'wheel',
            (event: WheelEvent) => {
                if (signal.aborted) {
                    return;
                }
                if (event.ctrlKey) {
                    return;
                }
                const deltaX = Number.isFinite(event.deltaX) ? event.deltaX : 0;
                const deltaY = Number.isFinite(event.deltaY) ? event.deltaY : 0;
                const isHorizontalIntent = Math.abs(deltaX) > Math.abs(deltaY) || event.shiftKey;
                if (!isHorizontalIntent) {
                    return;
                }
                if (shouldIgnoreCarouselWheelEvent({ viewport: inputArguments.viewport, eventTarget: event.target })) {
                    return;
                }
                event.preventDefault();

                const accumulator = this.#wheelAccumulatorByRoot.get(inputArguments.root) ?? 0;
                const nextAccumulator = accumulator + (event.shiftKey ? deltaY : deltaX);
                this.#wheelAccumulatorByRoot.set(inputArguments.root, nextAccumulator);
                const thresholdPx = 45;
                if (Math.abs(nextAccumulator) < thresholdPx) {
                    return;
                }
                this.#wheelAccumulatorByRoot.set(inputArguments.root, 0);
                const direction: ComparisonNavDirection = nextAccumulator > 0 ? 'next' : 'prev';
                const slideCount = inputArguments.resolveSlideCount();
                if (slideCount === null || slideCount <= 0) {
                    return;
                }
                this.#applyDirectionalSelection({
                    assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
                    slideCount,
                    direction,
                    selection: inputArguments.selection
                });
                inputArguments.onSelectionChanged();
            },
            { passive: false, signal }
        );

        inputArguments.viewport.addEventListener(
            'pointerdown',
            (event: PointerEvent) => {
                if (signal.aborted) {
                    return;
                }
                if (event.button !== 0) {
                    return;
                }
                if (!(event.target instanceof Element)) {
                    return;
                }
                const interactiveTarget = event.target.closest('button, a, input, textarea, select, [contenteditable="true"]');
                if (interactiveTarget) {
                    return;
                }
                const point = measureLayoutPoint(event, inputArguments.viewport);
                this.#dragStateByRoot.set(inputArguments.root, {
                    pointerId: event.pointerId,
                    startX: point.x,
                    startY: point.y,
                    lastX: point.x,
                    lastY: point.y,
                    isDragging: false
                });
            },
            { passive: true, signal }
        );

        inputArguments.viewport.addEventListener(
            'pointermove',
            (event: PointerEvent) => {
                if (signal.aborted) {
                    return;
                }
                const dragState = this.#dragStateByRoot.get(inputArguments.root) ?? null;
                if (!dragState || dragState.pointerId !== event.pointerId) {
                    return;
                }
                const point = measureLayoutPoint(event, inputArguments.viewport);
                dragState.lastX = point.x;
                dragState.lastY = point.y;
                const deltaX = dragState.lastX - dragState.startX;
                const deltaY = dragState.lastY - dragState.startY;
                if (!dragState.isDragging) {
                    const activationThreshold = 12;
                    if (Math.abs(deltaX) < activationThreshold || Math.abs(deltaX) < Math.abs(deltaY)) {
                        return;
                    }
                    dragState.isDragging = true;
                    inputArguments.viewport.setPointerCapture(event.pointerId);
                }
                event.preventDefault();
            },
            { passive: false, signal }
        );

        const finalizeDrag = (event: PointerEvent): void => {
            if (signal.aborted) {
                return;
            }
            const dragState = this.#dragStateByRoot.get(inputArguments.root) ?? null;
            if (!dragState || dragState.pointerId !== event.pointerId) {
                return;
            }
            this.#dragStateByRoot.delete(inputArguments.root);
            if (!dragState.isDragging) {
                return;
            }
            const deltaX = dragState.lastX - dragState.startX;
            const viewportWidth = Math.max(1, inputArguments.viewport.clientWidth);
            const thresholdRatio = 0.18;
            if (Math.abs(deltaX) < viewportWidth * thresholdRatio) {
                return;
            }
            const direction: ComparisonNavDirection = deltaX < 0 ? 'next' : 'prev';
            const slideCount = inputArguments.resolveSlideCount();
            if (slideCount === null || slideCount <= 0) {
                return;
            }
            this.#applyDirectionalSelection({
                assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
                slideCount,
                direction,
                selection: inputArguments.selection
            });
            inputArguments.onSelectionChanged();
        };

        inputArguments.viewport.addEventListener('pointerup', finalizeDrag, { passive: true, signal });
        inputArguments.viewport.addEventListener('pointercancel', finalizeDrag, { passive: true, signal });

        inputArguments.root.addEventListener(
            'keydown',
            (event: KeyboardEvent) => {
                if (signal.aborted) {
                    return;
                }
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
                    return;
                }
                const active = inputArguments.root.ownerDocument.activeElement;
                if (!(active instanceof Element) || inputArguments.root.contains(active) === false) {
                    return;
                }
                const activeTextTarget = active.closest('input, textarea, select, [contenteditable="true"]');
                if (activeTextTarget) {
                    return;
                }
                const direction: ComparisonNavDirection = event.key === 'ArrowLeft' ? 'prev' : 'next';
                const slideCount = inputArguments.resolveSlideCount();
                if (slideCount === null || slideCount <= 0) {
                    return;
                }
                this.#applyDirectionalSelection({
                    assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
                    slideCount,
                    direction,
                    selection: inputArguments.selection
                });
                inputArguments.onSelectionChanged();
                event.preventDefault();
            },
            { passive: false, signal }
        );
    }

    #applyDirectionalSelection(inputArguments: { assistantTurnTimestamp: number; slideCount: number; direction: ComparisonNavDirection; selection: ComparisonTurnSelectionController }): void {
        const current = inputArguments.selection.resolveActiveVariantIndexForVariantCount(inputArguments.assistantTurnTimestamp, inputArguments.slideCount);
        const nextIndex = inputArguments.direction === 'next' ? current + 1 : current - 1;
        inputArguments.selection.setManualSelection({
            assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
            variantCount: inputArguments.slideCount,
            nextActiveVariantIndex: nextIndex
        });
    }
}

export { ComparisonTurnCarouselInteractionController };

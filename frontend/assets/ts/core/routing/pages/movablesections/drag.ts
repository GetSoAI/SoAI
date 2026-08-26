/* SoAI - Shared routing drag [frontend/assets/ts/core/routing/pages/movablesections/drag.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint, type GeometryPoint } from '@core/layout/elementGeometry.ts';
import { getWindow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import type { MovableSectionId, MovableSectionLayoutContext } from '@core/routing/pages/movablesections/types.ts';
import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';

const handleMovableSectionDragMove = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, event: Event): void => {
    if (!(event instanceof PointerEvent)) return;
    const pointerEvent = event;
    const state = context.dragState;
    if (!state || pointerEvent.pointerId !== state.pointerId) return;
    pointerEvent.preventDefault();
    const point = measureLayoutPoint(pointerEvent, state.section);
    if (!state.dragStarted) {
        const deltaX = point.x - state.startX;
        const deltaY = point.y - state.startY;
        if (Math.hypot(deltaX, deltaY) < context.config.settings.dragThreshold) {
            return;
        }
        state.dragStarted = true;
        state.section.classList.add('is-dragging');
        context.gridElement?.setAttribute('data-dragging', 'true');
    }
    context.autoScroller?.update(point.y);
    context.refreshMetrics();
    updateDragPreview(context, point);
};

const updateDragPreview = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, point: GeometryPoint): void => {
    const state = context.dragState;
    const metrics = context.metrics;
    const gridElement = context.gridElement;
    if (!state || !metrics || !gridElement) return;
    const nextPosition = resolveDisplayGridPosition(point.x, point.y, state.span.width, state.grabOffsetX, state.grabOffsetY, context.getActiveColumns(), gridElement, metrics);
    if (nextPosition.x < 0 || nextPosition.y < 0 || nextPosition.x + state.span.width > context.getActiveColumns()) {
        state.previewLayout = null;
        state.pending = null;
        context.gridAnimator?.clearAllAnimations();
        return;
    }
    const animator = context.gridAnimator;
    if (!animator) return;
    const previewLayout = animator.computePreviewLayout(context.positions, state.id, nextPosition, state.span, context.getActiveColumns());
    const previewPosition = previewLayout.get(state.id) ?? { x: nextPosition.x, y: nextPosition.y, width: state.span.width, height: state.span.height };
    const deltaX = (previewPosition.x - state.origin.x) * (metrics.cellWidth + metrics.columnGap);
    const deltaY = (previewPosition.y - state.origin.y) * (metrics.cellHeight + metrics.rowGap);
    context.host.updateStyle(state.section, 'transform', `translate(${deltaX}px, ${deltaY}px) scale(${context.config.settings.dragScale})`);
    animator.animateToPreview(previewLayout, metrics);
    state.previewLayout = previewLayout;
    state.pending = { x: previewPosition.x, y: previewPosition.y, width: state.span.width, height: state.span.height };
};

const resolveDisplayGridPosition = (clientX: number, clientY: number, spanWidth: number, grabOffsetX: number, grabOffsetY: number, activeColumns: number, gridElement: HTMLElement, metrics: { paddingLeft: number; paddingTop: number; columnGap: number; rowGap: number; cellWidth: number; cellHeight: number }): { x: number; y: number } => {
    const gridRect = measureLayoutBox(gridElement);
    const sectionLeft = clientX - grabOffsetX;
    const sectionTop = clientY - grabOffsetY;
    const offsetX = sectionLeft - gridRect.left - metrics.paddingLeft;
    const offsetY = sectionTop - gridRect.top - metrics.paddingTop;
    const effectiveCellWidth = metrics.cellWidth + metrics.columnGap;
    const effectiveCellHeight = metrics.cellHeight + metrics.rowGap;
    if (effectiveCellWidth <= 0 || effectiveCellHeight <= 0) {
        throw new Error('Movable section grid metrics must be positive during drag');
    }
    const gridX = Math.round(offsetX / effectiveCellWidth);
    const gridY = Math.round(offsetY / effectiveCellHeight);
    const maxX = Math.max(0, activeColumns - spanWidth);
    return { x: clampNumber(gridX, 0, maxX), y: Math.max(0, gridY) };
};

const handleMovableSectionDragRelease = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, event: Event): void => {
    if (!(event instanceof PointerEvent)) return;
    const pointerEvent = event;
    const state = context.dragState;
    if (!state || pointerEvent.pointerId !== state.pointerId) return;
    pointerEvent.preventDefault();
    if (state.dragStarted) {
        endMovableSectionDrag(context);
        return;
    }
    cancelMovableSectionDrag(context);
};

const cancelMovableSectionDrag = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>): void => {
    if (!context.dragState) return;
    context.gridAnimator?.clearAllAnimations();
    context.applyLayout(context.getDisplayLayout());
    cleanupMovableSectionDrag(context);
};

const endMovableSectionDrag = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>): void => {
    const state = context.dragState;
    if (!state) return;
    context.gridAnimator?.clearAllAnimations();
    applyPreviewLayout(context, state.previewLayout, state.pending ?? state.origin, state.id, state.span);
    context.applyLayout(context.getDisplayLayout());
    context.notifyLayoutChanged();
    cleanupMovableSectionDrag(context);
};

const applyPreviewLayout = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, previewLayout: Map<string, GridPosition> | null, target: GridPosition, id: TSectionId, span: { width: number; height: number }): void => {
    if (previewLayout) {
        for (const [key, position] of previewLayout.entries()) {
            if (context.config.isSectionId(key)) {
                context.positions.set(key, { ...position });
            }
        }
        return;
    }
    context.positions.set(id, { x: target.x, y: target.y, width: span.width, height: span.height });
};

const registerMovableSectionDrag = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, section: HTMLElement, id: TSectionId): void => {
    const handle = context.host.optionalHTMLElement(context.config.dragHandleSelector, section);
    if (!handle) {
        return;
    }
    const onPointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent)) return;
        if (context.locked || event.button !== 0 || context.currentColumns !== context.config.settings.columns || context.dragState !== null) {
            return;
        }
        const target = event.target;
        if (target instanceof Element && target.closest(context.config.invalidDragSelector)) {
            return;
        }
        const sectionBounds = measureLayoutBox(section);
        const point = measureLayoutPoint(event, section);
        const storedPosition = context.positions.get(id);
        if (!sectionBounds.width || !sectionBounds.height || !storedPosition) {
            return;
        }
        context.dragState = {
            id,
            pointerId: event.pointerId,
            section,
            handle,
            origin: { ...storedPosition },
            startX: point.x,
            startY: point.y,
            dragStarted: false,
            grabOffsetX: point.x - sectionBounds.left,
            grabOffsetY: point.y - sectionBounds.top,
            span: { width: Math.max(1, storedPosition.width), height: Math.max(1, storedPosition.height) },
            previewLayout: null,
            pending: null,
            disposers: []
        };
        context.gridAnimator?.capturePositions(id, new Map<string, GridPosition>(context.positions));
        capturePointer(context, handle, event.pointerId);
        getLayoutRuntimeManager().setBodyStyle('userSelect', 'none');
        const windowTarget = getWindow();
        context.dragState.disposers.push(context.host.on(windowTarget, 'pointermove', (dragEvent: Event): void => handleMovableSectionDragMove(context, dragEvent)));
        context.dragState.disposers.push(context.host.on(windowTarget, 'pointerup', (dragEvent: Event): void => handleMovableSectionDragRelease(context, dragEvent)));
        context.dragState.disposers.push(context.host.on(windowTarget, 'pointercancel', (): void => cancelMovableSectionDrag(context)));
    };
    context.sectionDisposers.push(context.host.on(handle, 'pointerdown', onPointerDown));
};

const capturePointer = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>, handle: HTMLElement, pointerId: number): void => {
    if (!('setPointerCapture' in handle && typeof handle.setPointerCapture === 'function')) return;
    try {
        handle.setPointerCapture(pointerId);
    } catch (error) {
        const runtimeError = ensureError(error);
        context.host.logger('debug', context.config.logLabel, { name: runtimeError.name, message: runtimeError.message });
    }
};

const cleanupMovableSectionDrag = <TSectionId extends MovableSectionId>(context: MovableSectionLayoutContext<TSectionId>): void => {
    const state = context.dragState;
    if (!state) return;
    for (const dispose of state.disposers) {
        try {
            dispose();
        } catch (error) {
            const runtimeError = ensureError(error);
            context.host.logger('debug', context.config.logLabel, { name: runtimeError.name, message: runtimeError.message });
        }
    }
    try {
        state.handle.releasePointerCapture(state.pointerId);
    } catch (error) {
        const runtimeError = ensureError(error);
        context.host.logger('debug', context.config.logLabel, { name: runtimeError.name, message: runtimeError.message });
    }
    state.section.classList.remove('is-dragging');
    context.host.updateStyle(state.section, 'transform', '');
    context.gridAnimator?.clearSnapshot();
    context.gridElement?.removeAttribute('data-dragging');
    context.dragState = null;
    getLayoutRuntimeManager().clearBodyStyle('userSelect');
};

export { cancelMovableSectionDrag, registerMovableSectionDrag };

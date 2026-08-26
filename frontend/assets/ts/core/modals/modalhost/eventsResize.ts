/* SoAI - Shared modals events resize [frontend/assets/ts/core/modals/modalhost/eventsResize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { calculateAnchoredResize } from '@core/modals/modalhost/geometry.ts';
import { applyPosition, enforceBoundaries } from '@core/modals/modalhost/effects.ts';
import { applySizeConstraints } from '@core/modals/modalhost/sizePolicy.ts';
import { shouldPersistModalDesktopState } from '@core/modals/modalhost/layoutPolicy.ts';
import { getClientPoint } from '@core/modals/modalhost/guards.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const handleResizeStart = (state: ModalHostState, event: Event): void => {
    if (state.isMobileViewportState) {
        return;
    }

    const target = event.target;
    const targetElement = target instanceof Element ? target : null;
    const handleCandidate = targetElement?.closest?.('.modal-resize-handle');
    const handle = handleCandidate instanceof HTMLElement ? handleCandidate : null;
    const modalCandidate = handle?.closest('.ui-modal');
    const modal = modalCandidate instanceof HTMLElement ? modalCandidate : null;
    const contentCandidate = modal ? dom.resolve('.modal-content', modal) : null;
    const content = contentCandidate instanceof HTMLElement ? contentCandidate : null;
    if (!content || !modal) {
        return;
    }
    if (state.fullscreenState.has(modal.id)) {
        state.resizeState.delete(modal.id);
        return;
    }
    if (state.dragState.get(modal.id)?.isDragging || state.resizeState.get(modal.id)?.isResizing) {
        return;
    }

    const direction = handle?.dataset['direction'] || '';
    const point = getClientPoint(event, content);
    if (!point) {
        return;
    }

    const config = state.registry.getConfig(modal.id);
    const limits = applySizeConstraints({
        content,
        config,
        isMobileViewport: state.isMobileViewportState
    })?.limits;
    if (!limits) {
        return;
    }

    const rect = measureLayoutBox(content);
    state.resizeState.set(modal.id, {
        isResizing: true,
        startX: point.clientX,
        startY: point.clientY,
        startLeft: rect.left,
        startTop: rect.top,
        startRight: rect.right,
        startBottom: rect.bottom,
        minWidth: limits.minWidth,
        minHeight: limits.minHeight,
        maxWidth: limits.maxWidth,
        maxHeight: limits.maxHeight,
        edges: {
            top: direction.includes('top'),
            bottom: direction.includes('bottom'),
            left: direction.includes('left'),
            right: direction.includes('right')
        },
        modalContent: content
    });

    dom.addClass(dom.getBody(), 'resizing');
    event.preventDefault();
};

const handleResizeMove = (state: ModalHostState, event: Event): void => {
    const entry = Array.from(state.resizeState.entries()).find((item) => item[1].isResizing);
    if (!entry) {
        return;
    }
    const [id, resizeState] = entry;
    if (state.fullscreenState.has(id)) {
        state.resizeState.delete(id);
        dom.removeClass(dom.getBody(), 'resizing');
        return;
    }
    const point = getClientPoint(event, resizeState.modalContent);
    if (!point) {
        return;
    }

    const deltaX = point.clientX - resizeState.startX;
    const deltaY = point.clientY - resizeState.startY;
    const nextLayout = calculateAnchoredResize({
        resizeState,
        deltaX,
        deltaY,
        isMobileViewport: state.isMobileViewportState
    });

    dom.setStyles(resizeState.modalContent, { width: `${nextLayout.width}px`, height: `${nextLayout.height}px` });
    applyPosition(resizeState.modalContent, nextLayout.position);

    if (point.isTouch) {
        event.preventDefault();
    }
};

const handleResizeEnd = (state: ModalHostState): void => {
    const entry = Array.from(state.resizeState.entries()).find((item) => item[1].isResizing);
    if (!entry) {
        return;
    }
    const [id, resizeState] = entry;
    if (state.fullscreenState.has(id)) {
        state.resizeState.delete(id);
        dom.removeClass(dom.getBody(), 'resizing');
        return;
    }

    if (shouldPersistModalDesktopState(state.isMobileViewportState)) {
        const rect = measureLayoutBox(resizeState.modalContent);
        state.storage.setModalState(id, { size: { width: rect.width, height: rect.height } });
    }
    const rect = measureLayoutBox(resizeState.modalContent);
    enforceBoundaries({
        content: resizeState.modalContent,
        isMobileViewport: state.isMobileViewportState,
        sizeOverride: { width: rect.width, height: rect.height }
    });

    dom.removeClass(dom.getBody(), 'resizing');
    state.resizeState.delete(id);
};

export { handleResizeEnd, handleResizeMove, handleResizeStart };

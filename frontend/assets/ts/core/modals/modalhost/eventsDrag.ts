/* SoAI - Shared modals events drag [frontend/assets/ts/core/modals/modalhost/eventsDrag.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isEditableInteractionTarget } from '@core/dom/editableTargets.ts';
import { applyPosition, clampPosition } from '@core/modals/modalhost/effects.ts';
import { calculateModalPositionFromClientRect } from '@core/modals/modalhost/geometry.ts';
import { getClientPoint } from '@core/modals/modalhost/guards.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { toggleFullscreen } from '@core/modals/modalhost/eventsFullscreen.ts';
import { hideDockHint, shouldShowDockHint, showDockHint } from '@core/modals/modalhost/drag/dockHint.ts';
import { findActiveDragEntry, startDrag, updateTopSnapshotCandidate } from '@core/modals/modalhost/drag/dragState.ts';
import { startRestoreFromFullscreen } from '@core/modals/modalhost/drag/fullscreenRestore.ts';

const DRAG_ACTIVATE_THRESHOLD = 10;
const DRAG_ACTIVATE_THRESHOLD_SQUARED = DRAG_ACTIVATE_THRESHOLD * DRAG_ACTIVATE_THRESHOLD;
const MIN_MODAL_SIZE = 1;

const isMouseDoubleClick = (event: Event): boolean => event instanceof MouseEvent && event.detail > 1;

const handleDragStart = (state: ModalHostState, event: Event): void => {
    if (state.isMobileViewportState) {
        return;
    }

    if (isMouseDoubleClick(event)) {
        return;
    }

    const target = event.target;
    if (isEditableInteractionTarget(target)) {
        return;
    }

    const targetElement = target instanceof Element ? target : null;
    const handleCandidate = targetElement?.closest?.('.modal-header-top');
    const handle = handleCandidate instanceof HTMLElement ? handleCandidate : null;
    const modalCandidate = handle?.closest('.ui-modal');
    const modal = modalCandidate instanceof HTMLElement ? modalCandidate : null;
    const contentCandidate = modal ? dom.resolve('.modal-content', modal) : null;
    const content = contentCandidate instanceof HTMLElement ? contentCandidate : null;
    if (!content || !modal) {
        return;
    }

    const existingDrag = state.dragState.get(modal.id);
    if (existingDrag?.isDragging || existingDrag?.isFullscreenRestorePending || state.resizeState.get(modal.id)?.isResizing) {
        return;
    }

    const point = getClientPoint(event, content);
    if (!point) {
        return;
    }

    if (state.fullscreenState.has(modal.id)) {
        state.dragState.set(modal.id, {
            isDragging: false,
            isFullscreenRestorePending: true,
            startX: point.clientX,
            startY: point.clientY,
            offsetX: 0,
            offsetY: 0,
            pointerOffsetX: 0,
            pointerOffsetY: 0,
            contentWidth: 0,
            contentHeight: 0,
            isTopSnapshotCandidate: false,
            modalContent: content
        });

        if (point.isTouch) {
            event.preventDefault();
        }
        return;
    }

    startDrag(state, event, modal.id, point, content, handle);
};

const handleDragMove = (state: ModalHostState, event: Event): void => {
    const entry = findActiveDragEntry(state);
    if (!entry) {
        return;
    }

    const [id, dragState] = entry;
    const point = getClientPoint(event, dragState.modalContent);
    if (!point) {
        return;
    }

    if (dragState.isFullscreenRestorePending) {
        const deltaX = point.clientX - dragState.startX;
        const deltaY = point.clientY - dragState.startY;
        const distanceSq = deltaX * deltaX + deltaY * deltaY;
        if (distanceSq <= DRAG_ACTIVATE_THRESHOLD_SQUARED) {
            if (event.cancelable) {
                event.preventDefault();
            }
            return;
        }

        const modal = dom.resolve(`#${id}`);
        if (!(modal instanceof HTMLElement)) {
            state.dragState.delete(id);
            if (event.cancelable) {
                event.preventDefault();
            }
            return;
        }

        if (!startRestoreFromFullscreen(state, id, dragState, point, modal)) {
            if (event.cancelable) {
                event.preventDefault();
            }
            return;
        }
        return;
    }

    if (!dragState.isDragging) {
        return;
    }

    const nextSnapshotState = shouldShowDockHint(state, point.clientY, id) ? updateTopSnapshotCandidate(state, id, dragState, true) : updateTopSnapshotCandidate(state, id, dragState, false);

    if (nextSnapshotState.isTopSnapshotCandidate) {
        const modal = dom.resolve(`#${id}`);
        if (modal instanceof HTMLElement) {
            showDockHint(state, modal);
        } else {
            hideDockHint(state);
        }
    } else {
        hideDockHint(state);
    }

    const contentWidth = Math.max(dragState.contentWidth, MIN_MODAL_SIZE);
    const contentHeight = Math.max(dragState.contentHeight, MIN_MODAL_SIZE);
    const targetPosition = calculateModalPositionFromClientRect({
        content: dragState.modalContent,
        left: point.clientX - dragState.pointerOffsetX,
        top: point.clientY - dragState.pointerOffsetY,
        width: contentWidth,
        height: contentHeight,
        isMobileViewport: state.isMobileViewportState
    });
    const bounded = clampPosition({
        content: dragState.modalContent,
        position: targetPosition,
        isMobileViewport: state.isMobileViewportState,
        sizeOverride: {
            width: contentWidth,
            height: contentHeight
        }
    });
    applyPosition(dragState.modalContent, bounded);
    if (event.cancelable) {
        event.preventDefault();
    }
};

const handleDragEnd = (state: ModalHostState): void => {
    const entry = findActiveDragEntry(state);
    if (!entry) {
        return;
    }

    const [id, dragState] = entry;
    hideDockHint(state);
    const modalElement = dom.resolve(`#${id}`);
    const handle = dom.resolve('.modal-header-top', modalElement);
    if (handle) {
        dom.setStyle(handle, 'cursor', '');
    }

    if (!dragState.isDragging) {
        state.dragState.delete(id);
        return;
    }

    if (dragState.isTopSnapshotCandidate && modalElement instanceof HTMLElement) {
        if (toggleFullscreen(state, id)) {
            state.dragState.delete(id);
            return;
        }
    }

    state.dragState.delete(id);
};

export { handleDragEnd, handleDragMove, handleDragStart };

/* SoAI - Shared modals drag state [frontend/assets/ts/core/modals/modalhost/drag/dragState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { applyPosition, clampPosition, getTransformTranslate } from '@core/modals/modalhost/effects.ts';
import type { DragState } from '@core/modals/modalhost/types.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';

const MIN_MODAL_SIZE = 1;

const normalizeDragPosition = (content: HTMLElement, position: { x: number; y: number }, isMobileViewport: boolean, width: number, height: number): { x: number; y: number } => {
    const bounded = clampPosition({
        content,
        position,
        isMobileViewport,
        sizeOverride: { width, height }
    });
    const current = getTransformTranslate(content);
    if (!current || current.x !== bounded.x || current.y !== bounded.y) {
        applyPosition(content, bounded);
    }
    return bounded;
};

const updateTopSnapshotCandidate = (state: ModalHostState, id: string, dragState: DragState, isTopSnapshotCandidate: boolean): DragState => {
    if (dragState.isTopSnapshotCandidate === isTopSnapshotCandidate) {
        return dragState;
    }
    const nextState: DragState =
        dragState.isDragging === true
            ? {
                  isDragging: true,
                  isFullscreenRestorePending: false,
                  startX: dragState.startX,
                  startY: dragState.startY,
                  offsetX: dragState.offsetX,
                  offsetY: dragState.offsetY,
                  pointerOffsetX: dragState.pointerOffsetX,
                  pointerOffsetY: dragState.pointerOffsetY,
                  contentWidth: dragState.contentWidth,
                  contentHeight: dragState.contentHeight,
                  isTopSnapshotCandidate,
                  modalContent: dragState.modalContent
              }
            : {
                  isDragging: false,
                  isFullscreenRestorePending: true,
                  startX: dragState.startX,
                  startY: dragState.startY,
                  offsetX: dragState.offsetX,
                  offsetY: dragState.offsetY,
                  pointerOffsetX: dragState.pointerOffsetX,
                  pointerOffsetY: dragState.pointerOffsetY,
                  contentWidth: dragState.contentWidth,
                  contentHeight: dragState.contentHeight,
                  isTopSnapshotCandidate,
                  modalContent: dragState.modalContent
              };
    state.dragState.set(id, nextState);
    return nextState;
};

const findActiveDragEntry = (state: ModalHostState): [string, DragState] | null => {
    for (const [id, entry] of state.dragState.entries()) {
        if (entry.isDragging || entry.isFullscreenRestorePending) {
            return [id, entry];
        }
    }
    return null;
};

const startDrag = (state: ModalHostState, event: Event, modalId: string, point: { clientX: number; clientY: number; isTouch: boolean }, content: HTMLElement, handle: HTMLElement | null): void => {
    const rect = measureLayoutBox(content);
    const width = Math.max(rect.width, MIN_MODAL_SIZE);
    const height = Math.max(rect.height, MIN_MODAL_SIZE);
    const currentPosition = getTransformTranslate(content);
    const bounded = normalizeDragPosition(content, currentPosition ?? { x: 0, y: 0 }, state.isMobileViewportState, width, height);
    const pointerOffsetX = clampNumber(point.clientX - rect.left, 0, width);
    const pointerOffsetY = clampNumber(point.clientY - rect.top, 0, height);
    state.dragState.set(modalId, {
        isDragging: true,
        isFullscreenRestorePending: false,
        startX: point.clientX,
        startY: point.clientY,
        offsetX: bounded.x,
        offsetY: bounded.y,
        pointerOffsetX,
        pointerOffsetY,
        contentWidth: width,
        contentHeight: height,
        isTopSnapshotCandidate: false,
        modalContent: content
    });

    if (handle) {
        dom.setStyle(handle, 'cursor', 'grabbing');
    }
    if (point.isTouch) {
        event.preventDefault();
    }
};

export { findActiveDragEntry, startDrag, updateTopSnapshotCandidate };

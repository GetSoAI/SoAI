/* SoAI - Shared modals fullscreen restore [frontend/assets/ts/core/modals/modalhost/drag/fullscreenRestore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { MODAL_HEADER_FULLSCREEN_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { clampPosition } from '@core/modals/modalhost/effects.ts';
import { exitFullscreen } from '@core/modals/modalhost/eventsFullscreen.ts';
import { calculateModalPositionFromClientRect } from '@core/modals/modalhost/geometry.ts';
import type { DragState } from '@core/modals/modalhost/types.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';

const MIN_MODAL_SIZE = 1;

const pointerOffset = (clientAxis: number, origin: number, axisLength: number): number => {
    return clampNumber(clientAxis - origin, 0, axisLength);
};

const startRestoreFromFullscreen = (state: ModalHostState, id: string, dragState: DragState, point: { clientX: number; clientY: number }, modal: HTMLElement): boolean => {
    const toggleButton = dom.resolve(MODAL_HEADER_FULLSCREEN_SELECTOR, modal);
    const fullscreenState = state.fullscreenState.get(id);

    if (!(toggleButton instanceof HTMLElement) || !fullscreenState) {
        state.dragState.delete(id);
        return false;
    }

    const restoredWidth = Math.max(fullscreenState.previousSize.width, MIN_MODAL_SIZE);
    const restoredHeight = Math.max(fullscreenState.previousSize.height, MIN_MODAL_SIZE);
    const fullscreenRect = measureLayoutBox(dragState.modalContent);
    const fullscreenWidth = Math.max(fullscreenRect.width, MIN_MODAL_SIZE);
    const fullscreenHeight = Math.max(fullscreenRect.height, MIN_MODAL_SIZE);
    const mappedOffsetX = clampNumber((pointerOffset(point.clientX, fullscreenRect.left, fullscreenWidth) * restoredWidth) / fullscreenWidth, 0, restoredWidth);
    const mappedOffsetY = clampNumber((pointerOffset(point.clientY, fullscreenRect.top, fullscreenHeight) * restoredHeight) / fullscreenHeight, 0, restoredHeight);
    const targetPosition = calculateModalPositionFromClientRect({
        content: dragState.modalContent,
        left: point.clientX - mappedOffsetX,
        top: point.clientY - mappedOffsetY,
        width: restoredWidth,
        height: restoredHeight,
        isMobileViewport: state.isMobileViewportState
    });
    const bounded = clampPosition({
        content: dragState.modalContent,
        position: targetPosition,
        isMobileViewport: state.isMobileViewportState,
        sizeOverride: { width: restoredWidth, height: restoredHeight }
    });

    exitFullscreen(state, id, dragState.modalContent, toggleButton, true, bounded);
    state.dragState.set(id, {
        isDragging: true,
        isFullscreenRestorePending: false,
        startX: point.clientX,
        startY: point.clientY,
        offsetX: bounded.x,
        offsetY: bounded.y,
        pointerOffsetX: mappedOffsetX,
        pointerOffsetY: mappedOffsetY,
        contentWidth: restoredWidth,
        contentHeight: restoredHeight,
        isTopSnapshotCandidate: false,
        modalContent: dragState.modalContent
    });

    const headerTop = dom.resolve('.modal-header-top', modal);
    if (headerTop instanceof HTMLElement) {
        dom.setStyle(headerTop, 'cursor', 'grabbing');
    }
    return true;
};

export { startRestoreFromFullscreen };

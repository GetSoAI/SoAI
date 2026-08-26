/* SoAI - Shared frontend modal modalhost public contracts [frontend/assets/ts/core/modals/modalhost/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalConfig, Position, SavedModalState, Size } from '@core/modals/types.ts';

interface SizeLimits {
    minWidth: number;
    minHeight: number;
    maxWidth: number;
    maxHeight: number;
}

interface Boundaries {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

interface DragStateBase {
    startX: number;
    startY: number;
    offsetX: number;
    offsetY: number;
    pointerOffsetX: number;
    pointerOffsetY: number;
    contentWidth: number;
    contentHeight: number;
    isTopSnapshotCandidate: boolean;
    modalContent: HTMLElement;
}

interface DraggingState extends DragStateBase {
    isDragging: true;
    isFullscreenRestorePending: false;
}

interface FullscreenRestoreDragState extends DragStateBase {
    isDragging: false;
    isFullscreenRestorePending: true;
}

type DragState = DraggingState | FullscreenRestoreDragState;

interface ResizeState {
    isResizing: boolean;
    startX: number;
    startY: number;
    startLeft: number;
    startTop: number;
    startRight: number;
    startBottom: number;
    minWidth: number;
    minHeight: number;
    maxWidth: number;
    maxHeight: number;
    edges: {
        top: boolean;
        bottom: boolean;
        left: boolean;
        right: boolean;
    };
    modalContent: HTMLElement;
}

interface FullscreenState {
    previousPosition: Position;
    previousSize: Size;
}

interface ModalPageLockSnapshot {
    contentAriaHidden: string | null;
    contentInert: boolean;
    bodyModalLocked: string | null;
    bodyOverflow: string;
    pageOverflow: string | null;
}

interface SizeConstraintResult {
    width: number;
    height: number;
    limits: SizeLimits;
    changed: boolean;
}

interface ModalStorageApi {
    getModalState: (id: string) => SavedModalState | null;
    setModalState: (id: string, state: Partial<SavedModalState>) => void;
}

interface ClientPoint {
    clientX: number;
    clientY: number;
    isTouch: boolean;
}

interface ModalPositionDependencies {
    content: Element;
    position: Position;
    isMobileViewport: boolean;
    sizeOverride?: Size | null;
}

interface ModalBoundsDependencies {
    content: Element;
    isMobileViewport: boolean;
    sizeOverride?: Size | null;
}

interface ModalSizeDependencies {
    content: Element;
    config: ModalConfig;
    isMobileViewport: boolean;
    savedState?: SavedModalState | null | undefined;
    layoutOverride?: ModalConfig['size'] | undefined;
}

export type { Boundaries, ClientPoint, DragState, FullscreenState, ModalBoundsDependencies, ModalPageLockSnapshot, ModalPositionDependencies, ModalSizeDependencies, ModalStorageApi, ResizeState, SizeConstraintResult, SizeLimits };

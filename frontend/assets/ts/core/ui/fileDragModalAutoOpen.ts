/* SoAI - Shared file drag modal auto-open lifecycle [frontend/assets/ts/core/ui/fileDragModalAutoOpen.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocument, getWindow } from '@core/environment/public.ts';
import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { hasTransferFiles } from '@core/ui/fileDropArea.ts';

type FileDragEndReason = 'abort' | 'blur' | 'dragend' | 'leave' | 'drop';

interface FileDragModalAutoOpenBinding {
    root: HTMLElement;
    signal: AbortSignal;
    acceptsDrag?: (event: DragEvent) => boolean;
    canOpen: () => boolean;
    isModalOpen: () => boolean;
    openModal: () => void;
    closeModal: () => void;
    retainModalAfterDrop?: (event: DragEvent) => boolean;
}

const isDragPointInsideElement = (event: DragEvent, element: HTMLElement): boolean => {
    const rectangle = measureLayoutBox(element);
    const point = measureLayoutPoint(event, element);
    return point.x >= rectangle.left && point.x <= rectangle.right && point.y >= rectangle.top && point.y <= rectangle.bottom;
};

const isDragPointInsideViewport = (event: DragEvent, scope: Element): boolean => {
    const point = measureLayoutPoint(event, scope);
    const viewport = measureLayoutViewport(scope);
    return point.x > 0 && point.x < viewport.width && point.y > 0 && point.y < viewport.height;
};

const bindFileDragModalAutoOpen = (binding: FileDragModalAutoOpenBinding): void => {
    const documentTarget = getDocument();
    const windowTarget = getWindow();
    let activeSession = false;
    let modalRequested = false;
    let closeAutoOpenedModal = false;
    let modalWasOpenAtDragStart = false;
    const acceptsDrag = (event: DragEvent): boolean => binding.acceptsDrag?.(event) !== false;
    const captureDragStart = (): void => {
        if (activeSession) {
            return;
        }
        activeSession = true;
        modalWasOpenAtDragStart = binding.isModalOpen();
    };
    const clearDragSession = (): void => {
        activeSession = false;
        modalRequested = false;
        closeAutoOpenedModal = false;
        modalWasOpenAtDragStart = false;
    };
    const shouldRetainModal = (reason: FileDragEndReason, event?: DragEvent): boolean => {
        return reason === 'drop' && event !== undefined && binding.retainModalAfterDrop?.(event) === true;
    };
    const endDragSession = (reason: FileDragEndReason, event?: DragEvent): void => {
        try {
            if (activeSession && closeAutoOpenedModal && !shouldRetainModal(reason, event)) {
                binding.closeModal();
            }
        } finally {
            clearDragSession();
        }
    };
    const maybeOpen = (event: DragEvent): void => {
        if (!hasTransferFiles(event) || !acceptsDrag(event)) {
            return;
        }
        if (modalRequested) {
            return;
        }
        captureDragStart();
        try {
            if (!binding.canOpen()) {
                return;
            }
            modalRequested = true;
            closeAutoOpenedModal = !modalWasOpenAtDragStart;
            binding.openModal();
        } catch (error) {
            clearDragSession();
            throw error;
        }
    };
    const preventActiveFileDragDefault = (event: DragEvent): void => {
        if (!activeSession || !hasTransferFiles(event)) {
            return;
        }
        event.preventDefault();
    };
    const handleDrop = (event: DragEvent): void => {
        preventActiveFileDragDefault(event);
        endDragSession('drop', event);
    };
    const handleDocumentDragLeave = (event: DragEvent): void => {
        if (activeSession && event.relatedTarget === null && (!isDragPointInsideViewport(event, binding.root) || !isDragPointInsideElement(event, binding.root))) {
            endDragSession('leave', event);
        }
    };
    const handleDragEnd = (): void => endDragSession('dragend');
    const handleWindowBlur = (): void => endDragSession('blur');
    const handleAbort = (): void => endDragSession('abort');
    binding.root.addEventListener('dragenter', maybeOpen, { signal: binding.signal });
    binding.root.addEventListener(
        'dragover',
        (event: DragEvent): void => {
            if (!hasTransferFiles(event) || !acceptsDrag(event)) {
                return;
            }
            event.preventDefault();
            maybeOpen(event);
        },
        { signal: binding.signal }
    );
    binding.root.addEventListener(
        'dragleave',
        (event: DragEvent): void => {
            if (activeSession && !isDragPointInsideElement(event, binding.root)) {
                endDragSession('leave', event);
            }
        },
        { signal: binding.signal }
    );
    binding.root.addEventListener('drop', handleDrop, { signal: binding.signal });
    documentTarget.addEventListener('dragover', preventActiveFileDragDefault, { signal: binding.signal });
    documentTarget.addEventListener('dragleave', handleDocumentDragLeave, { signal: binding.signal });
    documentTarget.addEventListener('drop', handleDrop, { signal: binding.signal });
    windowTarget.addEventListener('dragend', handleDragEnd, { signal: binding.signal });
    windowTarget.addEventListener('blur', handleWindowBlur, { signal: binding.signal });
    binding.signal.addEventListener('abort', handleAbort, { once: true });
};

export { bindFileDragModalAutoOpen };
export type { FileDragModalAutoOpenBinding };

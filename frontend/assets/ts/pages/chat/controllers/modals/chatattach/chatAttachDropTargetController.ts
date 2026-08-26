/* SoAI - Chat attach modal drag-and-drop target controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDropTargetController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

type ChatAttachDropTargetBinderArguments = {
    element: HTMLElement;
    signal: AbortSignal;
    isEnabled?: () => boolean;
    acceptsDrop?: (event: DragEvent) => boolean;
    onFilesDropped: (files: File[], event: DragEvent) => Promise<void> | void;
    setTimer: (functionValue: () => void, delayMs: number) => number | null;
    clearTimer: (id: number | null | undefined) => void;
};

const hasTransferFiles = (event: DragEvent): boolean => {
    const transfer = event.dataTransfer;
    if (transfer === null) {
        return false;
    }
    if (transfer.items.length > 0) {
        for (const item of Array.from(transfer.items)) {
            if (item.kind === 'file') {
                return true;
            }
        }
    }
    return transfer.files.length > 0;
};

const bindChatAttachDropTarget = (inputArguments: ChatAttachDropTargetBinderArguments): void => {
    let dragDepth = 0;
    let dropAcceptedTimer: number | null = null;
    const isEnabled = (): boolean => inputArguments.isEnabled?.() !== false;
    const acceptsDrop = (event: DragEvent): boolean => inputArguments.acceptsDrop?.(event) !== false;
    const clearDragState = (): void => {
        dragDepth = 0;
        inputArguments.element.classList.remove('is-dragover');
    };
    const clearDropAcceptedState = (): void => {
        if (dropAcceptedTimer !== null) {
            inputArguments.clearTimer(dropAcceptedTimer);
            dropAcceptedTimer = null;
        }
        inputArguments.element.classList.remove('is-drop-accepted');
    };
    const pulseDropAcceptedState = (): void => {
        clearDropAcceptedState();
        measureLayoutBox(inputArguments.element);
        inputArguments.element.classList.add('is-drop-accepted');
        dropAcceptedTimer = inputArguments.setTimer(() => {
            dropAcceptedTimer = null;
            inputArguments.element.classList.remove('is-drop-accepted');
        }, 360);
    };
    inputArguments.signal.addEventListener('abort', clearDropAcceptedState, { once: true });
    inputArguments.element.addEventListener(
        'dragenter',
        (event: DragEvent): void => {
            if (!isEnabled() || !hasTransferFiles(event) || !acceptsDrop(event)) {
                return;
            }
            event.preventDefault();
            dragDepth += 1;
            inputArguments.element.classList.add('is-dragover');
        },
        { signal: inputArguments.signal }
    );
    inputArguments.element.addEventListener(
        'dragover',
        (event: DragEvent): void => {
            if (!isEnabled() || !hasTransferFiles(event) || !acceptsDrop(event)) {
                return;
            }
            event.preventDefault();
            if (event.dataTransfer !== null) {
                event.dataTransfer.dropEffect = 'copy';
            }
            inputArguments.element.classList.add('is-dragover');
        },
        { signal: inputArguments.signal }
    );
    inputArguments.element.addEventListener(
        'dragleave',
        (): void => {
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) {
                inputArguments.element.classList.remove('is-dragover');
            }
        },
        { signal: inputArguments.signal }
    );
    inputArguments.element.addEventListener(
        'drop',
        (event: DragEvent): void => {
            event.preventDefault();
            clearDragState();
            const transfer = event.dataTransfer;
            if (!isEnabled() || transfer === null || transfer.files.length === 0 || !acceptsDrop(event)) {
                return;
            }
            pulseDropAcceptedState();
            const dropResult = inputArguments.onFilesDropped(Array.from(transfer.files), event);
            if (dropResult !== undefined) {
                dropResult.catch((err) => {
                    errorHandler.warn('ChatAttachDropTarget', 'File drop handler failed', ensureError(err));
                });
            }
        },
        { signal: inputArguments.signal }
    );
};

export { bindChatAttachDropTarget, hasTransferFiles };

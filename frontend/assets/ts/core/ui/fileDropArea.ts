/* SoAI - Shared file drop area rendering and interaction [frontend/assets/ts/core/ui/fileDropArea.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';

interface FileDropAreaRenderConfig {
    id: string;
    action: string;
    title: string;
    hint: string;
    icons: readonly IconName[];
}

interface FileDropAreaBinding {
    element: HTMLElement;
    signal: AbortSignal;
    isEnabled?: () => boolean;
    acceptsDrop?: (event: DragEvent) => boolean;
    onFilesRejected?: (files: File[], event: DragEvent) => Promise<void> | void;
    onFilesDropped: (files: File[], event: DragEvent) => Promise<void> | void;
    setTimer: (callback: () => void, delayMs: number) => number | null;
    clearTimer: (id: number | null | undefined) => void;
}

const renderFileDropArea = (config: FileDropAreaRenderConfig): TrustedHtml => {
    const icons = joinUiHtml(config.icons.map((iconName) => uiHtml`<span class="ui-file-drop-area-icon" aria-hidden="true">${getIconSync(iconName, { size: 20, strokeWidth: 1.5 })}</span>`));
    return uiHtml`<button id="${uiAttr(config.id)}" class="ui-file-drop-area" type="button" aria-label="${uiAttr(config.title)}" data-tooltip="${uiAttr(config.title)}" data-action="${uiAttr(config.action)}">
        <span class="ui-file-drop-area-icons">${icons}</span>
        <span class="ui-file-drop-area-copy">
            <strong class="ui-file-drop-area-title">${config.title}</strong>
            <span class="ui-file-drop-area-hint">${config.hint}</span>
        </span>
    </button>`;
};

const transferAdvertisesFiles = (transfer: DataTransfer): boolean => Array.from(transfer.types).includes('Files');

const hasTransferFiles = (event: DragEvent): boolean => {
    const transfer = event.dataTransfer;
    if (transfer === null) {
        return false;
    }
    for (const item of Array.from(transfer.items)) {
        if (item.kind === 'file') {
            return true;
        }
    }
    return transfer.files.length > 0 || transferAdvertisesFiles(transfer);
};

const transferHasSingleFileMatching = (event: DragEvent, matches: (file: File) => boolean): boolean => {
    const transfer = event.dataTransfer;
    if (transfer === null) {
        return false;
    }
    const transferredFiles = Array.from(transfer.files);
    if (transferredFiles.length > 0) {
        const file = transferredFiles[0];
        return transferredFiles.length === 1 && file !== undefined && matches(file);
    }
    const fileItems = Array.from(transfer.items).filter((item) => item.kind === 'file');
    if (fileItems.length === 0) {
        return transferAdvertisesFiles(transfer);
    }
    if (fileItems.length !== 1) {
        return false;
    }
    const file = fileItems[0]?.getAsFile() ?? null;
    return file === null || matches(file);
};

const executeFileDropHandler = (handler: () => Promise<void> | void): void => {
    try {
        const result = handler();
        if (result === undefined) {
            return;
        }
        result.catch((error) => {
            errorHandler.warn('FileDropArea', 'File drop handler failed', ensureError(error));
        });
    } catch (error) {
        errorHandler.warn('FileDropArea', 'File drop handler failed', ensureError(error));
    }
};

const bindFileDropArea = (binding: FileDropAreaBinding): void => {
    let dragDepth = 0;
    let acceptedStateTimer: number | null = null;
    const isEnabled = (): boolean => binding.isEnabled?.() !== false;
    const acceptsDrop = (event: DragEvent): boolean => binding.acceptsDrop?.(event) !== false;
    const clearDragState = (): void => {
        dragDepth = 0;
        binding.element.classList.remove('is-dragover');
    };
    const clearAcceptedState = (): void => {
        if (acceptedStateTimer !== null) {
            binding.clearTimer(acceptedStateTimer);
            acceptedStateTimer = null;
        }
        binding.element.classList.remove('is-drop-accepted');
    };
    const pulseAcceptedState = (): void => {
        clearAcceptedState();
        measureLayoutBox(binding.element);
        binding.element.classList.add('is-drop-accepted');
        acceptedStateTimer = binding.setTimer(() => {
            acceptedStateTimer = null;
            binding.element.classList.remove('is-drop-accepted');
        }, 360);
        if (acceptedStateTimer === null) {
            binding.element.classList.remove('is-drop-accepted');
        }
    };
    const clearStates = (): void => {
        clearDragState();
        clearAcceptedState();
    };
    binding.signal.addEventListener('abort', clearStates, { once: true });
    binding.element.addEventListener(
        'dragenter',
        (event: DragEvent): void => {
            if (!isEnabled() || !hasTransferFiles(event) || !acceptsDrop(event)) {
                return;
            }
            event.preventDefault();
            dragDepth += 1;
            binding.element.classList.add('is-dragover');
        },
        { signal: binding.signal }
    );
    binding.element.addEventListener(
        'dragover',
        (event: DragEvent): void => {
            if (!isEnabled() || !hasTransferFiles(event) || !acceptsDrop(event)) {
                clearDragState();
                return;
            }
            event.preventDefault();
            if (event.dataTransfer !== null) {
                event.dataTransfer.dropEffect = 'copy';
            }
            binding.element.classList.add('is-dragover');
        },
        { signal: binding.signal }
    );
    binding.element.addEventListener(
        'dragleave',
        (): void => {
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) {
                binding.element.classList.remove('is-dragover');
            }
        },
        { signal: binding.signal }
    );
    binding.element.addEventListener(
        'drop',
        (event: DragEvent): void => {
            clearStates();
            if (!hasTransferFiles(event)) {
                return;
            }
            event.preventDefault();
            const transfer = event.dataTransfer;
            if (!isEnabled() || transfer === null || transfer.files.length === 0) {
                return;
            }
            const files = Array.from(transfer.files);
            if (!acceptsDrop(event)) {
                executeFileDropHandler(() => binding.onFilesRejected?.(files, event));
                return;
            }
            pulseAcceptedState();
            executeFileDropHandler(() => binding.onFilesDropped(files, event));
        },
        { signal: binding.signal }
    );
};

export { bindFileDropArea, hasTransferFiles, renderFileDropArea, transferHasSingleFileMatching };
export type { FileDropAreaBinding, FileDropAreaRenderConfig };

/* SoAI - Attachment dialog picker and file drop interaction [frontend/assets/ts/features/attachmodal/AttachUploadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindFileDropArea } from '@core/ui/fileDropArea.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import type { AttachDraftListController } from '@features/attachmodal/AttachDraftListController.ts';
import type { AttachUploadElements } from '@features/attachmodal/contracts.ts';

interface AttachUploadConsumer {
    isEnabled(): boolean;
    allowFolders: boolean;
    beforePicker(): void;
    fileInput(): HTMLInputElement;
    folderInput(): HTMLInputElement;
    captureUpload(): (files: File[], source: 'file' | 'folder') => Promise<void>;
    classifyDrop(event: DragEvent, files: File[]): 'file' | 'folder';
    run(task: () => Promise<void>): void;
    setTimer(callback: () => void, delayMs: number): number | null;
    clearTimer(id: number | null | undefined): void;
}

const openAttachFilePicker = (input: HTMLInputElement): void => {
    if (typeof input.showPicker === 'function') input.showPicker();
    else input.click();
};

class AttachUploadController {
    readonly #consumer: AttachUploadConsumer;
    readonly #elements: AttachUploadElements;
    readonly #drafts: AttachDraftListController;

    constructor(consumer: AttachUploadConsumer, elements: AttachUploadElements, signal: AbortSignal, drafts: AttachDraftListController) {
        this.#consumer = consumer;
        this.#elements = elements;
        this.#drafts = drafts;
        bindFileDropArea({
            element: elements.dropzoneButton,
            signal,
            setTimer: (callback, delay) => consumer.setTimer(callback, delay),
            clearTimer: (id) => consumer.clearTimer(id),
            isEnabled: () => consumer.isEnabled(),
            acceptsDrop: (event) => consumer.isEnabled() && (consumer.allowFolders || consumer.classifyDrop(event, Array.from(event.dataTransfer?.files ?? [])) === 'file'),
            onFilesDropped: (files, event) => {
                if (!consumer.isEnabled()) return;
                const source = consumer.classifyDrop(event, files);
                if (source === 'folder' && !consumer.allowFolders) return;
                const upload = consumer.captureUpload();
                consumer.run(() => upload(files, source));
            }
        });
        this.#sync();
    }

    activate(): void {
        this.#drafts.activate();
        this.#sync();
    }
    deactivate(): void {
        this.#drafts.deactivate();
    }
    openPrimaryPicker(): void {
        this.openFiles();
    }
    openFiles(): void {
        if (!this.#consumer.isEnabled()) return;
        this.#consumer.beforePicker();
        openAttachFilePicker(this.#consumer.fileInput());
    }
    openFolder(): void {
        if (!this.#consumer.isEnabled() || !this.#consumer.allowFolders) return;
        this.#consumer.beforePicker();
        openAttachFilePicker(this.#consumer.folderInput());
    }
    #sync(): void {
        setControlDisabledState(this.#elements.dropzoneButton, !this.#consumer.isEnabled());
        setControlDisabledState(this.#elements.filesButton, !this.#consumer.isEnabled());
        setControlDisabledState(this.#elements.folderButton, !this.#consumer.isEnabled() || !this.#consumer.allowFolders);
    }
}

export { AttachUploadController, openAttachFilePicker };
export type { AttachUploadConsumer };

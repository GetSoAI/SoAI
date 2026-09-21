/* SoAI - Chat attach modal upload tab controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachUploadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachUploadHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { ChatAttachDraftAttachmentListController } from '@pages/chat/controllers/modals/chatattach/ChatAttachDraftAttachmentListController.ts';
import { acceptsUploadDrop } from '@pages/chat/controllers/modals/chatattach/chatAttachDropAcceptanceController.ts';
import { bindChatAttachDropTarget } from '@pages/chat/controllers/modals/chatattach/chatAttachDropTargetController.ts';
import { resolveChatAttachDroppedPayloadType } from '@pages/chat/controllers/modals/chatattach/chatAttachDroppedPayloadController.ts';
import type { ChatAttachUploadElements } from '@pages/chat/controllers/modals/chatattach/types.ts';
import { openFilePicker, setButtonEnabled } from '@pages/chat/controllers/modals/chatattach/view.ts';

class ChatAttachUploadController {
    readonly #host: ChatAttachUploadHost;
    readonly #elements: ChatAttachUploadElements;
    readonly #signal: AbortSignal;
    readonly #draftListController: ChatAttachDraftAttachmentListController;

    constructor(host: ChatAttachUploadHost, elements: ChatAttachUploadElements, signal: AbortSignal) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#draftListController = new ChatAttachDraftAttachmentListController(host, elements.draftList, signal, 'upload');
        this.#bind();
        this.#syncControls();
    }

    activate(): void {
        this.#draftListController.activate();
        this.#syncControls();
    }

    deactivate(): void {
        this.#draftListController.deactivate();
    }

    openPrimaryPicker(): void {
        if (this.#host.attachments.fileUploadEnabled()) {
            this.openFiles();
            return;
        }
        this.openFolder();
    }

    openFiles(): void {
        if (!this.#host.attachments.fileUploadEnabled()) {
            return;
        }
        this.#host.conversation.actions.collapseSidebarIfNarrowViewport();
        openFilePicker(this.#host.attachments.requireFileInput());
    }

    openFolder(): void {
        if (!this.#host.attachments.fileUploadEnabled()) {
            return;
        }
        this.#host.conversation.actions.collapseSidebarIfNarrowViewport();
        openFilePicker(this.#host.attachments.requireFolderInput());
    }

    async uploadDroppedFiles(files: File[]): Promise<void> {
        if (!this.#host.attachments.fileUploadEnabled()) {
            return;
        }
        await this.#host.attachments.uploadFiles(files);
    }

    async uploadDroppedFolder(files: File[]): Promise<void> {
        if (!this.#host.attachments.fileUploadEnabled()) {
            return;
        }
        await this.#host.attachments.uploadFolder(files);
    }

    #bind(): void {
        bindChatAttachDropTarget({
            element: this.#elements.dropzoneButton,
            signal: this.#signal,
            setTimer: (functionValue, delayMs) => this.#host.shared.pageResources.setTimer(functionValue, delayMs),
            clearTimer: (id) => this.#host.shared.pageResources.clearTimer(id),
            isEnabled: () => this.#host.attachments.fileUploadEnabled(),
            acceptsDrop: (event) => acceptsUploadDrop(this.#host, event),
            onFilesDropped: (files, event) =>
                this.#host.execution.run('chat:attachModalUploadDrop', async () => {
                    const payloadType = resolveChatAttachDroppedPayloadType(event, files);
                    if (payloadType === 'folder') {
                        await this.uploadDroppedFolder(files);
                        return;
                    }
                    await this.uploadDroppedFiles(files);
                })
        });
    }

    #syncControls(): void {
        const fileUploadEnabled = this.#host.attachments.fileUploadEnabled();
        setButtonEnabled(this.#elements.dropzoneButton, fileUploadEnabled);
        setButtonEnabled(this.#elements.filesButton, fileUploadEnabled);
        setButtonEnabled(this.#elements.folderButton, fileUploadEnabled);
    }
}

export { ChatAttachUploadController };

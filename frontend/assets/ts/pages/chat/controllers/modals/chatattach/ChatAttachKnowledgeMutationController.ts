/* SoAI - Chat attach modal linked knowledge mutation controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeMutationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagDocumentsPage } from '@features/chat/public.ts';
import { isChatAttachKnowledgeSourceEnabled, readChatAttachKnowledgeCapabilities } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts';
import { ChatAttachKnowledgeOperations, type KnowledgeSource } from '@pages/chat/controllers/modals/chatattach/service.ts';
import { setButtonEnabled } from '@pages/chat/controllers/modals/chatattach/view.ts';

type ChatAttachKnowledgeMutationControllerArguments = {
    operations: ChatAttachKnowledgeOperations;
    refresh: () => Promise<void>;
    readConversationId: () => string | null;
    readPage: () => RagDocumentsPage | null;
    writePageOffset: (offset: number) => void;
};

class ChatAttachKnowledgeMutationController {
    readonly #operations: ChatAttachKnowledgeOperations;
    readonly #refresh: () => Promise<void>;
    readonly #readConversationId: () => string | null;
    readonly #readPage: () => RagDocumentsPage | null;
    readonly #writePageOffset: (offset: number) => void;

    constructor(inputArguments: ChatAttachKnowledgeMutationControllerArguments) {
        this.#operations = inputArguments.operations;
        this.#refresh = inputArguments.refresh;
        this.#readConversationId = inputArguments.readConversationId;
        this.#readPage = inputArguments.readPage;
        this.#writePageOffset = inputArguments.writePageOffset;
    }

    async handleInput(input: HTMLInputElement, source: KnowledgeSource): Promise<void> {
        if (!isChatAttachKnowledgeSourceEnabled(readChatAttachKnowledgeCapabilities(), source)) {
            input.value = '';
            return;
        }
        if (!input.files || input.files.length === 0) {
            return;
        }
        const selectedFiles = Array.from(input.files);
        input.value = '';
        if (await this.#operations.upload(selectedFiles, source)) {
            await this.#refresh();
        }
    }

    async uploadDroppedFiles(files: File[], source: KnowledgeSource): Promise<void> {
        if (files.length === 0 || !isChatAttachKnowledgeSourceEnabled(readChatAttachKnowledgeCapabilities(), source)) {
            return;
        }
        if (await this.#operations.upload(files, source)) {
            await this.#refresh();
        }
    }

    async deleteDocument(button: HTMLButtonElement): Promise<void> {
        const documentId = button.dataset['docId'] ?? null;
        setButtonEnabled(button, false);
        if (await this.#operations.deleteDocument(this.#readConversationId(), documentId)) {
            await this.#refresh();
            return;
        }
        setButtonEnabled(button, true);
    }

    async changePage(button: HTMLElement): Promise<void> {
        const offsetValue = button.dataset['ragOffset'] ?? null;
        const nextOffset = offsetValue === null ? Number.NaN : Number(offsetValue);
        const page = this.#readPage();
        if (!Number.isFinite(nextOffset) || !Number.isInteger(nextOffset) || nextOffset < 0 || page === null) {
            return;
        }
        this.#writePageOffset(nextOffset);
        await this.#refresh();
    }
}

export { ChatAttachKnowledgeMutationController };

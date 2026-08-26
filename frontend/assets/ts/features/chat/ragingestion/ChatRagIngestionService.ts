/* SoAI - Chat feature RAG ingestion service [frontend/assets/ts/features/chat/ragingestion/ChatRagIngestionService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatRagIngestionServiceContract, ChatRagIngestionStartArguments } from '@core/chat/protocols.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import type { ChatPageApi, RagIngestionStatus } from '@features/chat/public.ts';
import { RagIngestionController } from '@features/chat/ragingestion/RagIngestionController.ts';
import { syncRagIngestionTaskOperation } from '@features/chat/ragingestion/RagIngestionTaskOperationManager.ts';

type ChatRagIngestionServiceDependencies = {
    api: ChatPageApi;
};

class ChatRagIngestionService implements ChatRagIngestionServiceContract {
    readonly #controller: RagIngestionController;
    readonly #statusChanges = new ChangeNotificationSource();

    constructor(dependencies: ChatRagIngestionServiceDependencies) {
        const ragApi = dependencies.api.webui.chat.rag;
        this.#controller = new RagIngestionController({
            runWithBoundary: async <T>(_name: string, functionValue: () => Promise<T>): Promise<T> => await functionValue(),
            listDocuments: async (conversationId, options) => await ragApi.listDocuments(conversationId, options),
            uploadDocumentsBatch: async (conversationId, files, options) => await ragApi.uploadDocumentsBatch(conversationId, files, options),
            cancelKnowledgeAttachment: async (conversationId, knowledgeAttachmentId, options) => await dependencies.api.webui.chat.attachments.knowledge.cancel(conversationId, knowledgeAttachmentId, options),
            resolveAbortSignal: () => null,
            onStatusChange: (status) => this.#handleStatusChange(status)
        });
    }

    getStatusForConversation(conversationId: string): RagIngestionStatus | null {
        return this.#controller.getStatusForConversation(conversationId);
    }

    async start(inputArguments: ChatRagIngestionStartArguments): Promise<void> {
        await this.#controller.start(inputArguments);
    }

    async cancel(conversationId: string): Promise<void> {
        await this.#controller.cancel(conversationId);
    }

    subscribe(handler: () => void): () => void {
        return this.#statusChanges.subscribe(handler);
    }

    #handleStatusChange(status: RagIngestionStatus | null): void {
        syncRagIngestionTaskOperation(status, (conversationId) => this.#controller.cancel(conversationId));
        this.#statusChanges.notify();
    }
}

export { ChatRagIngestionService };
export type { ChatRagIngestionServiceDependencies };

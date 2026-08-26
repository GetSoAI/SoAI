/* SoAI - Chat attach modal linked knowledge progress [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createTaskOperationPanel, type TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import { CHAT_ATTACH_MODAL_ID, type RagIngestionStatus } from '@features/chat/public.ts';

const PROGRESS_CONTAINER_ID = modalUiId(CHAT_ATTACH_MODAL_ID, 'knowledge-progress');

class ChatAttachKnowledgeProgressController {
    #panel: TaskOperationPanel | null = null;
    #conversationId: string | null = null;

    attach(conversationId: string | null): void {
        this.#conversationId = conversationId;
        this.#panel?.detach();
        this.#panel = null;
        if (conversationId !== null) {
            this.#panel = this.#createPanel(conversationId);
            this.#panel.attach();
        }
    }

    setConversation(conversationId: string | null): void {
        this.#conversationId = conversationId;
        if (conversationId === null) {
            this.detach();
            return;
        }
        if (this.#panel === null) {
            this.#panel = this.#createPanel(conversationId);
            this.#panel.attach();
            return;
        }
        this.#panel?.refreshFilter({
            types: ['rag-document-upload', 'rag-url-fetch', 'rag-folder-scan'],
            conversationId
        });
    }

    sync(status: RagIngestionStatus | null, cancelHandler: (() => void) | null): void {
        const conversationId = this.#conversationId;
        if (conversationId === null) {
            return;
        }
        const progressKey = this.#progressKey(conversationId);
        if (status === null || status.conversationId !== conversationId || status.state === 'submitted' || status.state === 'cancelled') {
            requireTaskOperationsApi().removeLocalOperation(progressKey);
            return;
        }
        requireTaskOperationsApi().upsertLocalOperation({
            id: progressKey,
            type: 'rag-document-upload',
            pluginName: 'RAG',
            progress: this.#progressPercent(status),
            cancelable: Boolean(cancelHandler),
            cancel: cancelHandler ?? undefined,
            meta: {
                convId: conversationId,
                displayName: i18n.t('chat.ingestion.title'),
                statusMessage: this.#progressDetails(status),
                taskStatus: status.state
            }
        });
    }

    detach(): void {
        this.#panel?.detach();
        this.#panel = null;
    }

    clear(): void {
        if (this.#conversationId !== null) {
            requireTaskOperationsApi().removeLocalOperation(this.#progressKey(this.#conversationId));
        }
        this.#conversationId = null;
        this.detach();
    }

    #progressKey(conversationId: string): string {
        return `rag-ingestion:${conversationId}`;
    }

    #createPanel(conversationId: string): TaskOperationPanel {
        return createTaskOperationPanel({
            container: PROGRESS_CONTAINER_ID,
            filter: {
                types: ['rag-document-upload', 'rag-url-fetch', 'rag-folder-scan'],
                conversationId
            }
        });
    }

    #progressPercent(status: RagIngestionStatus): number {
        if (status.total <= 0) {
            return status.state === 'submitted' ? 100 : 0;
        }
        if (status.state === 'submitted') {
            return 100;
        }
        const processed = status.succeeded + status.failed + status.skipped;
        return Math.round(clampNumber((processed / status.total) * 100, 0, 99));
    }

    #progressDetails(status: RagIngestionStatus): string {
        if (status.failed > 0 && status.lastError) {
            return status.lastError;
        }
        if (status.state === 'paused') {
            return i18n.t('chat.ingestion.status.paused', this.#progressArguments(status));
        }
        return i18n.t('chat.ingestion.status.running', this.#progressArguments(status));
    }

    #progressArguments(status: RagIngestionStatus): Record<string, number> {
        return {
            completed: status.succeeded,
            total: status.total,
            queued: status.queued,
            'in_flight': status.inFlight,
            failed: status.failed,
            skipped: status.skipped
        };
    }
}

export { ChatAttachKnowledgeProgressController };

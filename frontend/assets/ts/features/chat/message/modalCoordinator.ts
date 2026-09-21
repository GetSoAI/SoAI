/* SoAI - Chat message modal coordinator [frontend/assets/ts/features/chat/message/modalCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatKnowledgeAttachmentsApi, ChatSoaiPathsApi } from '@features/chat/pagecontracts/types.ts';
import { ChatAttachmentOverflowModal } from '@features/chat/message/attachmentoverflowmodal/service.ts';
import type { AttachmentOverflowShowArguments } from '@features/chat/message/attachmentoverflowmodal/showArgs.ts';
import { ChatMessageInfoModal } from '@features/chat/message/messageinfomodal/service.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';

type ChatMessageModalCoordinatorDependencies = CopyActionDependencies & {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems' | 'delete'>;
    soaiPathsApi: Pick<ChatSoaiPathsApi, 'preview' | 'read' | 'download' | 'open' | 'token'>;
    escapeHtml: (value: string) => string;
    getAttachmentDraftRevision: () => number;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
};

class ChatMessageModalCoordinator {
    readonly #messageInfoModal: ChatMessageInfoModal;
    readonly #attachmentOverflowModal: ChatAttachmentOverflowModal;

    constructor(dependencies: ChatMessageModalCoordinatorDependencies) {
        this.#messageInfoModal = new ChatMessageInfoModal({
            escapeHtml: (value: string): string => dependencies.escapeHtml(value),
            runWithBoundary: (name, functionValue) => dependencies.runWithBoundary(name, functionValue),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            copyToClipboard: (text, options) => dependencies.copyToClipboard(text, options),
            showNotification: (message, type) => dependencies.showNotification(message, type)
        });
        this.#attachmentOverflowModal = new ChatAttachmentOverflowModal({
            knowledgeAttachmentsApi: dependencies.knowledgeAttachmentsApi,
            soaiPathsApi: dependencies.soaiPathsApi,
            runWithBoundary: (name, functionValue) => dependencies.runWithBoundary(name, functionValue),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            copyToClipboard: (text, options) => dependencies.copyToClipboard(text, options),
            showNotification: (message, type) => dependencies.showNotification(message, type),
            getAttachmentDraftRevision: () => dependencies.getAttachmentDraftRevision(),
            onKnowledgeAttachmentChanged: (summary) => dependencies.onKnowledgeAttachmentChanged(summary)
        });
    }

    dispose(): void {
        this.#attachmentOverflowModal.dispose();
    }

    showMessageInfo(message: ChatMessage): void {
        this.#messageInfoModal.show(message);
    }

    showAttachmentOverflow(inputArguments: AttachmentOverflowShowArguments): void {
        this.#attachmentOverflowModal.show(inputArguments);
    }
}

export { ChatMessageModalCoordinator };

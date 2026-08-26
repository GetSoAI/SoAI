/* SoAI - Chat attachment manager constructor contracts [frontend/assets/ts/features/chat/attachments/attachmentManagerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationAttachmentChangedEvent } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import type { ChatAttachmentUIManager } from '@features/chat/ChatTypes.ts';
import type { ChatAttachmentProcessorContract } from '@features/chat/attachments/attachmentProcessingQueue.ts';
import type { SoaiPathImagePreviewLoader } from '@features/chat/attachments/soaiPathImagePreviewLifecycle.ts';

interface ChatAttachmentErrorHandler {
    (error: Error, title: string, options?: { notify?: boolean }): void;
}

interface ChatAttachmentManagerOptions {
    attachmentProcessor: ChatAttachmentProcessorContract;
    uiManager: ChatAttachmentUIManager;
    logger: ModuleLogger;
    errorHandler: ChatAttachmentErrorHandler;
    deletePhysicalAttachment?: ((conversationId: string, attachmentId: string) => Promise<void>) | null;
    subscribeAttachmentChanged?: ((listener: (event: ConversationAttachmentChangedEvent) => void) => () => void) | null;
    loadSoaiPathImagePreview?: SoaiPathImagePreviewLoader | null;
}

export type { ChatAttachmentErrorHandler, ChatAttachmentManagerOptions };

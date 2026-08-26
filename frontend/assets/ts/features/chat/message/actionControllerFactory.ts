/* SoAI - Chat message action controller factory [frontend/assets/ts/features/chat/message/actionControllerFactory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { ChatMessageActions } from '@features/chat/message/actions.ts';
import type { ChatMessageDeleteUndoController } from '@features/chat/message/messageDeleteUndoController.ts';
import type { ChatMessageModalCoordinator } from '@features/chat/message/modalCoordinator.ts';
import type { ResolvedMessageReference } from '@features/chat/message/messageReferenceResolution.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { ChatMessageManagerDependencies } from '@features/chat/message/types.ts';

interface ChatMessageActionControllerHost {
    getIcon(name: IconName, options?: IconOptions): TrustedHtml;
    resolveMessageReference(conversation: ConversationContract | null, messageId: string): ResolvedMessageReference;
    resolveMessageContentSegments(message: ChatMessage | null | undefined): MessageSegment[];
    renderMessageTextContent(message: ChatMessage): string;
    resolveMessageContainer(messageId: string): HTMLElement | null;
    isShowActivitiesEnabled(): boolean;
    toggleLoadingActivityCollapsedState(message: ChatMessage, defaultCollapsed: boolean): boolean;
    invalidateMessageCache(message: ChatMessage | null | undefined): void;
    postRender(container: Element | null): void;
}

const createChatMessageActions = (inputArguments: { dependencies: ChatMessageManagerDependencies; domChangeTarget: EventTarget; host: ChatMessageActionControllerHost; deleteUndoController: ChatMessageDeleteUndoController; modalCoordinator: ChatMessageModalCoordinator }): ChatMessageActions =>
    new ChatMessageActions({
        runtime: inputArguments.dependencies.runtime,
        session: {
            getCurrentConversation: () => inputArguments.dependencies.session.getCurrentConversation(),
            getCurrentRunningActivitySnapshot: () => inputArguments.dependencies.session.getCurrentRunningActivitySnapshot(),
            getCurrentModel: () => inputArguments.dependencies.session.getCurrentModel(),
            getModelStreamHasPayload: () => inputArguments.dependencies.session.getModelStreamHasPayload(),
            isModelAvailable: (modelId) => inputArguments.dependencies.session.isModelAvailable(modelId)
        },
        presentation: {
            domChangeTarget: inputArguments.domChangeTarget,
            getIcon: (name, options) => inputArguments.host.getIcon(name, options),
            resolveMessageReference: (conversation, messageId) => inputArguments.host.resolveMessageReference(conversation, messageId),
            resolveMessageContentSegments: (message) => inputArguments.host.resolveMessageContentSegments(message),
            renderMessageTextContent: (message) => inputArguments.host.renderMessageTextContent(message),
            resolveMessageContainer: (messageId) => inputArguments.host.resolveMessageContainer(messageId),
            revealActivityElement: (element) => inputArguments.dependencies.rendering.revealActivityElement(element),
            isShowActivitiesEnabled: () => inputArguments.host.isShowActivitiesEnabled(),
            toggleLoadingActivityCollapsedState: (message, defaultCollapsed) => inputArguments.host.toggleLoadingActivityCollapsedState(message, defaultCollapsed),
            invalidateMessageCache: (message) => inputArguments.host.invalidateMessageCache(message),
            postRender: (container) => inputArguments.host.postRender(container)
        },
        interaction: {
            runWithBoundary: (name, functionValue) => inputArguments.dependencies.interaction.runWithBoundary(name, functionValue),
            hasClipboardSupport: () => inputArguments.dependencies.interaction.hasClipboardSupport(),
            copyToClipboard: (text, options) => inputArguments.dependencies.interaction.copyToClipboard(text, options),
            showNotification: (message, type) => inputArguments.dependencies.interaction.showNotification(message, type),
            showMessageModal: (message) => inputArguments.modalCoordinator.showMessageInfo(message),
            showAttachmentOverflowModal: (modalArguments) => inputArguments.modalCoordinator.showAttachmentOverflow(modalArguments),
            requestMessageDelete: (conversation, messageDomId) => inputArguments.deleteUndoController.requestDelete(conversation, messageDomId),
            commitMessageDeleteNow: (conversation, messageDomId) => inputArguments.deleteUndoController.commitDeleteNow(conversation, messageDomId),
            undoMessageDelete: (conversation, messageDomId) => inputArguments.deleteUndoController.undoDelete(conversation, messageDomId)
        }
    });

export { createChatMessageActions };

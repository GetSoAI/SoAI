/* SoAI - Chat message action dependency contract [frontend/assets/ts/features/chat/message/actionDeps.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { AttachmentOverflowShowArguments } from '@features/chat/message/attachmentoverflowmodal/showArgs.ts';
import type { MessageReferenceResolver } from '@features/chat/message/messageReferenceResolution.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import type { ChatMessageRuntimeOperations } from '@features/chat/message/runtimeOperations.ts';
import type { ConversationRunningActivitySnapshot } from '@features/chat/storage/storageModels.ts';

interface ChatMessageActionData {
    timestamp?: string | null;
    knowledgeAttachmentId?: string | null;
    callId?: string | null;
    assistantTurnTs?: string | null;
    modelVariantIndex?: string | null;
    actionElement?: HTMLElement | null;
}

interface ChatMessageActionSessionPort {
    getCurrentConversation: () => ConversationContract | null;
    getCurrentRunningActivitySnapshot: () => ConversationRunningActivitySnapshot | null;
    getCurrentModel: () => string | null;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
}

interface ChatMessageActionPresentationPort {
    domChangeTarget: EventTarget;
    getIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    resolveMessageReference: MessageReferenceResolver;
    resolveMessageContentSegments: (message: ChatMessage) => MessageSegment[];
    renderMessageTextContent: (message: ChatMessage) => string;
    resolveMessageContainer: (messageId: string) => HTMLElement | null;
    revealActivityElement: (element: HTMLElement) => void;
    isShowActivitiesEnabled: () => boolean;
    toggleLoadingActivityCollapsedState: (message: ChatMessage, defaultCollapsed: boolean) => boolean;
    invalidateMessageCache: (message: ChatMessage | null | undefined) => void;
    postRender: (container: Element | null) => void;
}

interface ChatMessageActionInteractionPort extends CopyActionDependencies {
    showMessageModal: (message: ChatMessage) => void;
    showAttachmentOverflowModal: (inputArguments: AttachmentOverflowShowArguments) => void;
    requestMessageDelete: (conversation: ConversationContract, messageDomId: string) => Promise<void>;
    commitMessageDeleteNow: (conversation: ConversationContract, messageDomId: string) => Promise<void>;
    undoMessageDelete: (conversation: ConversationContract, messageDomId: string) => Promise<void>;
}

interface ChatMessageActionsDependencies {
    runtime: ChatMessageRuntimeOperations;
    session: ChatMessageActionSessionPort;
    presentation: ChatMessageActionPresentationPort;
    interaction: ChatMessageActionInteractionPort;
}

export type { ChatMessageActionData, ChatMessageActionsDependencies };

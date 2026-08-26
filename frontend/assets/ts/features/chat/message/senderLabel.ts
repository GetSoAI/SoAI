/* SoAI - Chat message sender label resolution [frontend/assets/ts/features/chat/message/senderLabel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString, toTrimmedStringOrNull } from '@core/normalize.ts';
import type { ChatUiParameters } from '@core/types/chatParameters.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { isMessagingAccountConversation } from '@features/chat/conversation/conversationSettingsEligibility.ts';

type MessageSenderLabelContext = {
    message: ChatMessage;
    role: string;
    parameters: ChatUiParameters;
    conversation: ConversationContract | null;
    currentModel: string | null;
    getModelDisplayName(modelId: string | null): string;
};

type ConversationExportUserSenderLabelContext = {
    conversation: ConversationContract | null;
    message: ChatMessage | null;
    fallbackLabel: string;
};

const resolveMessagingParticipantName = (message: ChatMessage | null): string | null => {
    if (message === null) {
        return null;
    }
    return toTrimmedStringOrNull(message.messagingSenderDisplayName) ?? toTrimmedStringOrNull(message.messagingSenderId);
};

const resolveIdentityUserName = (conversation: ConversationContract | null): string | null => {
    return toTrimmedStringOrNull(conversation?.modelSettings?.identity?.userDisplayName);
};

const resolveSelectableModelId = (value: string | null | undefined): string | null => {
    return toTrimmedString(value) ? (value ?? null) : null;
};

const resolveLiveUserSenderLabel = (context: MessageSenderLabelContext): string => {
    return resolveIdentityUserName(context.conversation) ?? resolveMessagingParticipantName(context.message) ?? i18n.t('chat.message.you');
};

const resolveConversationExportUserSenderLabel = (context: ConversationExportUserSenderLabelContext): string => {
    const identityName = resolveIdentityUserName(context.conversation);
    const participantName = resolveMessagingParticipantName(context.message);
    if (isMessagingAccountConversation(context.conversation)) {
        return participantName ?? identityName ?? context.fallbackLabel;
    }
    return identityName ?? participantName ?? context.fallbackLabel;
};

const resolveAssistantSenderLabel = (context: MessageSenderLabelContext): string => {
    const preferredModelId = resolveSelectableModelId(context.message.modelId) ?? resolveSelectableModelId(context.conversation?.modelSettings?.model) ?? resolveSelectableModelId(context.currentModel);
    const modelDisplayName = context.getModelDisplayName(preferredModelId);
    const realModelName = modelDisplayName ? modelDisplayName : i18n.t('chat.message.assistant');
    const assistantDisplayName = toTrimmedStringOrNull(context.conversation?.modelSettings?.identity?.assistantDisplayName);
    if (assistantDisplayName === null) {
        return realModelName;
    }
    if (context.parameters.hideRealModel === true) {
        return assistantDisplayName;
    }
    return i18n.t('chat.message.assistantWithModel', { assistant: assistantDisplayName, model: realModelName });
};

const resolveNonUserSenderLabel = (context: MessageSenderLabelContext): string => {
    if (context.role === 'assistant') {
        return resolveAssistantSenderLabel(context);
    }
    return context.role ? context.role.charAt(0).toUpperCase() + context.role.slice(1) : i18n.t('chat.message.assistant');
};

const resolveMessageSenderLabel = (context: MessageSenderLabelContext): string => {
    return context.role === 'user' ? resolveLiveUserSenderLabel(context) : resolveNonUserSenderLabel(context);
};

const resolveConversationExportSenderLabel = (context: MessageSenderLabelContext): string => {
    if (context.role !== 'user') {
        return resolveNonUserSenderLabel(context);
    }
    return resolveConversationExportUserSenderLabel({
        conversation: context.conversation,
        message: context.message,
        fallbackLabel: i18n.t('chat.message.you')
    });
};

export { resolveConversationExportSenderLabel, resolveConversationExportUserSenderLabel, resolveMessageSenderLabel };
export type { ConversationExportUserSenderLabelContext, MessageSenderLabelContext };

/* SoAI - Chat page create voice call controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createVoiceCallController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { extractSpeechTextFromMarkdown, stripPreviewReferenceTokensForPlainText, type MessageSegment } from '@features/chat/public.ts';
import { resolveVoiceSttSettings, resolveVoiceTtsSettings } from '@pages/chat/controllers/voice/service.ts';
import { VoiceCallController } from '@pages/chat/controllers/voicecall/VoiceCallController.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatPageElementsHost } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatMessageSendingOwner } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

interface ChatVoiceCallConversationPort extends ChatConversationStateHost, ChatSettingsStateHost, ChatConversationViewHost, ChatMessageSendingOwner {}

interface ChatVoiceCallRuntimePort extends ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatPageElementsHost, ChatRuntimeServicesHost, ChatVoiceSessionHost, PageFeedbackOwnerHost {}

interface ChatVoiceCallDependencies extends ChatVoiceCallConversationPort, ChatVoiceCallRuntimePort {
    api: ApiClient;
}

const resolveVoiceCallSegmentText = (segment: MessageSegment): string => {
    if (segment.type === 'text') {
        const markdown = stripPreviewReferenceTokensForPlainText(segment.text).trim();
        return markdown ? extractSpeechTextFromMarkdown(markdown) : '';
    }
    if (segment.type === 'soai_path') {
        return segment.virtualPath;
    }
    if (segment.type === 'soai_file') {
        return segment.filename;
    }
    return '';
};

const resolveVoiceCallSpeechText = (segments: MessageSegment[]): string => {
    const fragments: string[] = [];
    for (const segment of segments) {
        const text = resolveVoiceCallSegmentText(segment).trim();
        if (text) {
            fragments.push(text);
        }
    }
    return fragments.join('\n').trim();
};

const createChatVoiceCallController = (page: ChatVoiceCallDependencies): VoiceCallController => {
    return new VoiceCallController({
        feedback: page.feedback,
        apiClient: page.api,
        runtimeAssets: page.runtimeServices.voiceCallAssets,
        chatStreamService: page.runtimeServices.chatStream,
        isConversationStreaming: (conversationId) => {
            const normalizedConversationId = toTrimmedString(conversationId);
            return normalizedConversationId ? page.conversationView.isStreaming(normalizedConversationId) : false;
        },
        interruptStreaming: (conversationId, reason) => page.turnRuntime.requireStreaming().interruptStreaming(conversationId, reason),
        waitForConversationIdle: (conversationId, signal) => page.turnRuntime.requireStreaming().waitForConversationIdle(conversationId, signal),
        resolveMessageContentSegments: (message) => page.conversationRuntime.requireMessages().resolveMessageContentSegments(message),
        resolveAssistantSpeechText: (segments) => resolveVoiceCallSpeechText(segments),
        cancelAudioRecording: () => page.voiceSession.cancelRecording(),
        getCurrentConversationId: () => page.conversationState.currentConversationId,
        getCurrentModel: () => page.conversationState.currentModel,
        sendVoiceMessage: (text, attachmentContent, signal, beforeSend) => page.messageSending.sendQueuedTextMessage(text, attachmentContent, signal, beforeSend),
        updateCallButtonState: (active) => page.elements.updateCallButtonState(active),
        resolveTtsSettings: () => {
            return resolveVoiceTtsSettings(page.settings.parameters);
        },
        resolveSttModel: () => resolveVoiceSttSettings(page.settings.parameters).model
    });
};

export { createChatVoiceCallController };
export type { ChatVoiceCallDependencies };

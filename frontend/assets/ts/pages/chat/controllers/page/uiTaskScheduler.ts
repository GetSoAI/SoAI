/* SoAI - Chat page UI task scheduler [frontend/assets/ts/pages/chat/controllers/page/uiTaskScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createUiTaskScheduler, type UiTaskRoute, type UiTaskScheduler, type UiTaskSchedulerHost } from '@core/concurrency/uiTaskScheduler.ts';

type ChatUiTaskSchedulerHost = UiTaskSchedulerHost;
type ChatUiTaskScheduler = UiTaskScheduler;

const isSendMessageOperation = (operationId: string): boolean => {
    return operationId.startsWith('chat:sendMessage:');
};

const isModelControlOperation = (operationId: string): boolean => {
    return operationId.startsWith('chat:modelControl:');
};

const resolveChatUiTaskRoute = (operationId: string): UiTaskRoute => {
    if (isSendMessageOperation(operationId)) {
        return { key: operationId, policy: 'serialize' };
    }
    if (isModelControlOperation(operationId)) {
        return { key: 'chat:modelControl', policy: 'serialize' };
    }
    if (operationId.startsWith('chat:stopStreaming:')) {
        return { key: operationId, policy: 'drop-if-busy' };
    }
    if (operationId === 'chat:presetLibrary:refresh') {
        return { key: 'chat:presetLibrary', policy: 'latest-wins' };
    }
    if (operationId.startsWith('chat:presetLibrary:')) {
        return { key: 'chat:presetLibrary', policy: 'serialize' };
    }
    if (operationId === 'chat:conversationSwitch') {
        return { key: 'chat:conversationActivation', policy: 'start-latest' };
    }
    if (operationId === 'chat:conversationNavigation' || operationId === 'chat:batchOperation' || operationId === 'chat:openArchivedConversation' || operationId === 'chat:openArchivedConversations') {
        return { key: 'chat:conversationSelection', policy: 'serialize' };
    }
    if (operationId === 'chat:modelChange') {
        return { key: 'chat:modelChange', policy: 'latest-wins' };
    }
    if (operationId === 'chat:parameterInput' || operationId === 'chat:parameterChange') {
        return { key: 'chat:parameterUpdate', policy: 'latest-wins' };
    }
    if (operationId === 'chat:fileUpload' || operationId === 'chat:cameraUpload' || operationId === 'chat:folderUpload' || operationId === 'chat:documentUpload') {
        return { key: 'chat:attachmentsUpload', policy: 'serialize' };
    }
    if (operationId === 'chat:renderConversationList') {
        return { key: 'chat:renderConversationList', policy: 'latest-wins' };
    }
    if (operationId === 'chat:refreshConversationMetadata') {
        return { key: 'chat:refreshConversationMetadata', policy: 'latest-wins' };
    }
    if (operationId === 'chat:renderCurrentConversation') {
        return { key: 'chat:renderCurrentConversation', policy: 'latest-wins' };
    }
    if (operationId === 'chat:refreshConversationsUI') {
        return { key: 'chat:refreshConversationsUI', policy: 'latest-wins' };
    }
    return { key: operationId, policy: 'serialize' };
};

const createChatUiTaskScheduler = (host: ChatUiTaskSchedulerHost): ChatUiTaskScheduler => {
    return createUiTaskScheduler(host, resolveChatUiTaskRoute);
};

export { createChatUiTaskScheduler };
export type { ChatUiTaskScheduler, ChatUiTaskSchedulerHost };

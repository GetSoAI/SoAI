/* SoAI - Chat page configuration side effects [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/chatPageConfigurationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN } from '@core/chat/parameters/textZoom.ts';
import { getLogValidation } from '@core/logvalidation/public.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatPageApi, ConversationWorkspacePathConfig, McpConfig } from '@features/chat/public.ts';
import { validateTextZoomValue } from '@pages/chat/controllers/page/dom/validation.ts';
import { applyMcpConfigToConversationModelSettings, updateConversationWorkspacePathConfig } from '@pages/chat/controllers/page/state.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

const log = createModuleLogger('ChatPage', { defaultLevel: 'info' });

interface ChatPageConfigurationHost extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, ChatConversationViewHost {
    api: ChatPageApi;
}

const normalizedWorkspacePath = (value: JsonValue | undefined): string => (typeof value === 'string' ? value.trim() : '');
const normalizedWorkspaceFingerprint = (value: JsonValue | undefined): string => (typeof value === 'string' ? value.trim() : '');

const applyConversationMcpConfig = (host: ChatPageConfigurationHost, conversationId: string, config: McpConfig): void => {
    const applied = applyMcpConfigToConversationModelSettings({ conversations: host.conversationState.conversations, saveState: (force?: boolean): void => host.conversationRuntime.requireStorage().saveState(force) }, conversationId, config);
    if (applied && host.conversationState.currentConversationId === conversationId) {
        host.composerSurface.requireUi().updateInputState();
    }
};

const applyConversationWorkspacePathConfig = (host: ChatPageConfigurationHost, conversationId: string, config: ConversationWorkspacePathConfig): void => {
    const conversation = host.conversationState.conversations.get(conversationId);
    const previousWorkspacePath = normalizedWorkspacePath(conversation?.modelSettings.workspacePath);
    const previousWorkspaceFingerprint = normalizedWorkspaceFingerprint(conversation?.effectiveWorkspaceRootFingerprint);
    const nextWorkspacePath = normalizedWorkspacePath(config.workspacePath);
    const nextWorkspaceFingerprint = normalizedWorkspaceFingerprint(config.effectiveRootFingerprint);
    const applied = updateConversationWorkspacePathConfig({ conversations: host.conversationState.conversations, saveState: (force?: boolean): void => host.conversationRuntime.requireStorage().saveState(force) }, conversationId, config);
    if (applied && host.conversationState.currentConversationId === conversationId && (previousWorkspacePath !== nextWorkspacePath || previousWorkspaceFingerprint !== nextWorkspaceFingerprint)) {
        const soaiLinkResolution = host.composerSurface.requireSoaiLinkResolution();
        host.composerSurface.requireAttachments().discardSoaiPathDraftAttachments((record) => soaiLinkResolution.materializeRecord(record));
    }
};

const validateChatPageTextZoomValue = (zoom: number | null, contextMessage: string): number | null => {
    return validateTextZoomValue(
        (value: number | null) => {
            const result = getLogValidation().validateTextZoom(value);
            if (!result.valid || result.zoom === null) {
                return result;
            }
            if (result.zoom < CHAT_TEXT_ZOOM_MIN || result.zoom > CHAT_TEXT_ZOOM_MAX) {
                return {
                    valid: false,
                    zoom: null,
                    error: `Text zoom ${result.zoom} is outside the allowed range ${CHAT_TEXT_ZOOM_MIN}-${CHAT_TEXT_ZOOM_MAX}`
                };
            }
            return result;
        },
        (message: string, error?: Error): void => log('error', message, error),
        zoom,
        contextMessage
    );
};

export { applyConversationMcpConfig, applyConversationWorkspacePathConfig, validateChatPageTextZoomValue };

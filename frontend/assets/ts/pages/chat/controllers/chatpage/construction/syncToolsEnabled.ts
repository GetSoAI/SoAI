/* SoAI - Chat page sync tools enabled [frontend/assets/ts/pages/chat/controllers/chatpage/construction/syncToolsEnabled.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { canInteractivelyAdjustConversationTools, isChatConversationSettingsWritable, parseMcpConfig, type Conversation } from '@features/chat/public.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatPreferencesHost } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface SyncToolsEnabledHost extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatPreferencesHost, ChatUiTaskScopeHost, ChatConversationViewHost {
    api: ApiClient;
    composer: {
        refreshTokenCounterPreview(): void;
    };
    applyInputActionVisibility(): void;
}

const refreshTokenCounterPreviewIfCurrent = (host: SyncToolsEnabledHost, conversationId: string): void => {
    if (host.conversationView.current()?.id !== conversationId) {
        return;
    }
    host.composer.refreshTokenCounterPreview();
};

const syncMcpConfigToConversation = async (host: SyncToolsEnabledHost, conversationId: string, patch: { toolsEnabled?: boolean; toolApprovalRequired?: boolean }): Promise<void> => {
    const conversation = host.conversationView.current();
    if (!canInteractivelyAdjustConversationTools(conversation)) {
        return;
    }
    if (conversation.id !== conversationId) {
        return;
    }
    const modelSettings = conversation.modelSettings;
    const mcpSettings = modelSettings.mcp;
    const currentToolsEnabled = mcpSettings?.toolsEnabled ?? null;
    const currentToolApprovalRequired = mcpSettings?.toolApprovalRequired ?? null;
    const nextToolsEnabled = patch.toolsEnabled === true || patch.toolsEnabled === false ? patch.toolsEnabled : null;
    const nextToolApprovalRequired = patch.toolApprovalRequired === true || patch.toolApprovalRequired === false ? patch.toolApprovalRequired : null;
    const hasEffectiveChange = (nextToolsEnabled !== null && currentToolsEnabled !== nextToolsEnabled) || (nextToolApprovalRequired !== null && currentToolApprovalRequired !== nextToolApprovalRequired);
    const currentModel = modelSettings.model;
    const resolvedModel = typeof currentModel === 'string' ? currentModel : null;
    const nextSettings: Conversation['modelSettings'] = { ...modelSettings, model: resolvedModel };
    const nextMcp = mcpSettings ? { ...mcpSettings } : { defaultTools: [], planTools: [], executeTools: [], serverConfigs: {}, toolsEnabled: true, toolApprovalRequired: true };
    if (patch.toolsEnabled === true || patch.toolsEnabled === false) {
        nextMcp.toolsEnabled = patch.toolsEnabled;
    }
    if (patch.toolApprovalRequired === true || patch.toolApprovalRequired === false) {
        nextMcp.toolApprovalRequired = patch.toolApprovalRequired;
    }
    nextSettings.mcp = nextMcp;
    const previousModelSettings = conversation.modelSettings;
    if (hasEffectiveChange) {
        conversation.modelSettings = nextSettings;
    }
    host.composerSurface.requireUi().updateInputState();
    host.applyInputActionVisibility();
    host.conversationRuntime.requireStorage().saveState(true);
    if (!hasEffectiveChange) {
        return;
    }
    if (!isChatConversationSettingsWritable(conversation)) {
        refreshTokenCounterPreviewIfCurrent(host, conversationId);
        return;
    }
    if (!host.conversationRuntime.requireConversation().isConversationPersisted(conversationId)) {
        refreshTokenCounterPreviewIfCurrent(host, conversationId);
        return;
    }
    await host.taskScope.runAsync('chat:syncMcpConfig', async () => {
        try {
            const mcpApi = host.api.webui.chat.mcp;
            const response = await mcpApi.updateConfig(conversationId, patch);
            if (conversation.modelSettings !== nextSettings) {
                return;
            }
            const config = parseMcpConfig(response);
            host.preferences.applyMcpConfig(conversationId, config);
            host.composerSurface.requireUi().updateInputState();
            refreshTokenCounterPreviewIfCurrent(host, conversationId);
        } catch (error) {
            if (conversation.modelSettings !== nextSettings) {
                return;
            }
            conversation.modelSettings = previousModelSettings;
            host.composerSurface.requireUi().updateInputState();
            host.applyInputActionVisibility();
            host.conversationRuntime.requireStorage().saveState(true);
            refreshTokenCounterPreviewIfCurrent(host, conversationId);
            throw error;
        }
    });
};

const syncToolsEnabledToConversation = async (host: SyncToolsEnabledHost, enabled: boolean): Promise<void> => {
    const conversation = host.conversationView.current();
    if (!canInteractivelyAdjustConversationTools(conversation) || isConversationAuthorityLocked(conversation)) {
        return;
    }
    const conversationId = conversation.id;
    if (!conversationId) {
        return;
    }
    await syncMcpConfigToConversation(host, conversationId, { toolsEnabled: enabled });
};

const syncToolApprovalRequiredToConversation = async (host: SyncToolsEnabledHost, required: boolean): Promise<void> => {
    const conversation = host.conversationView.current();
    if (!canInteractivelyAdjustConversationTools(conversation) || isConversationAuthorityLocked(conversation)) {
        return;
    }
    const conversationId = conversation.id;
    if (!conversationId) {
        return;
    }
    await syncMcpConfigToConversation(host, conversationId, { toolApprovalRequired: required });
};

export { syncToolsEnabledToConversation };
export { syncToolApprovalRequiredToConversation };
export type { SyncToolsEnabledHost };

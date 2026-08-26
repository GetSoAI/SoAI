/* SoAI - Chat feature configuration open flow [frontend/assets/ts/features/chat/conversationsettings/configurationOpenFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { loadConversationSettings } from '@features/chat/conversationsettings/actions.ts';
import type { ConversationSettingsControllerBundle } from '@features/chat/conversationsettings/controllerRegistry.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { ConversationWorkspacePathConfig, SearchConfig } from '@features/chat/conversationsettings/settingsModels.ts';

interface ConversationSettingsOpenFlowArguments {
    host: ConversationSettingsHost;
    controllers: ConversationSettingsControllerBundle;
    modal: Element | null;
    defaultToolsModal: Element | null;
    readConversationId(): string | null;
    resetState(conversationId: string | null): void;
    nextLoadToken(): number;
    isLoadTokenActive(token: number): boolean;
    isIdentityPromptsDirty(): boolean;
    writeSearchConfig(config: SearchConfig | null): void;
    writeWorkspacePathConfig(config: ConversationWorkspacePathConfig | null): void;
}

const openConversationSettings = async (inputArguments: ConversationSettingsOpenFlowArguments): Promise<void> => {
    const { controllers, host } = inputArguments;
    const conversation = host.data.getCurrentConversation();
    const conversationId = conversation?.id ?? null;
    if (!isChatConversationSettingsWritable(conversation)) {
        if (inputArguments.readConversationId() !== null) {
            inputArguments.resetState(null);
        }
        controllers.workspacePathController.setConversation(null);
        controllers.identityPromptsController.syncFromConversation(null);
        return;
    }
    if (inputArguments.readConversationId() !== conversationId) {
        inputArguments.resetState(conversationId);
    }
    controllers.workspacePathController.setConversation(conversationId);
    controllers.identityPromptsController.syncFromConversation(conversation);
    if (!conversationId) {
        return;
    }
    const operation = loadConversationSettings({
        conversation,
        host,
        loadToken: inputArguments.nextLoadToken(),
        modal: inputArguments.modal,
        defaultToolsModal: inputArguments.defaultToolsModal,
        ragController: controllers.ragController,
        mcpController: controllers.mcpController,
        onConversationPersisted: (persistedConversation) => {
            controllers.workspacePathController.setConversation(persistedConversation.id ?? null);
            if (!inputArguments.isIdentityPromptsDirty()) {
                controllers.identityPromptsController.syncFromConversation({
                    ...conversation,
                    ...persistedConversation,
                    messages: conversation.messages
                });
            }
        },
        setSearchConfig: (config) => {
            inputArguments.writeSearchConfig(config);
        },
        setWorkspacePathConfig: (config) => {
            inputArguments.writeWorkspacePathConfig(config);
            controllers.workspacePathController.syncFromConfig(config);
            if (conversation.id && config) {
                host.workflow.updateConversationWorkspacePathConfig(conversation.id, config);
            }
        },
        isLoadTokenActive: (token) => inputArguments.isLoadTokenActive(token)
    });
    terminateHandledPromise(operation);
    return operation;
};

export { openConversationSettings };

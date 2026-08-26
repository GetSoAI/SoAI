/* SoAI - Chat feature controller registry [frontend/assets/ts/features/chat/conversationsettings/controllerRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireConversationSettingsChatApi, type ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { runDisposerCallbacks } from '@features/chat/controllerLifecycle.ts';
import { applyConversationSectionApplyState, applyConversationSettingsUpdate } from '@features/chat/conversationsettings/effects.ts';
import { resolveSectionApplyStateTransition } from '@features/chat/conversationsettings/actions.ts';
import { ConversationWorkspacePathSettingsController } from '@features/chat/conversationsettings/workspacepathsettingscontroller/service.ts';
import { IdentityPromptsConversationSettingsController } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/service.ts';
import { McpConversationSettingsController } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/service.ts';
import { RagConversationSettingsController } from '@features/chat/conversationsettings/ragconversationsettings/service/RagConversationSettingsController.ts';
import type { SettingsState } from '@features/chat/conversationsettings/settingsModels.ts';
import type { ConversationSettingsSection, ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';

interface ConversationSettingsControllerBundle {
    workspacePathController: ConversationWorkspacePathSettingsController;
    identityPromptsController: IdentityPromptsConversationSettingsController;
    mcpController: McpConversationSettingsController;
    ragController: RagConversationSettingsController;
}

interface ConversationSettingsControllerRegistryArguments {
    host: ConversationSettingsHost;
    readConversationId: () => string | null;
    readLoadToken: () => number;
    readSectionState: () => ConversationSettingsSectionState;
    writeSectionState: (state: ConversationSettingsSectionState) => void;
    readState: () => SettingsState;
    writeRagConfig: (config: SettingsState['ragConfig']) => void;
    writeMcpConfig: (config: SettingsState['mcpConfig']) => void;
    writeMcpTools: (tools: SettingsState['mcpTools']) => void;
    writeMcpCanonicalToolDefaults: (defaults: SettingsState['mcpCanonicalToolDefaults']) => void;
    refreshKnowledgeManagedMcpState: () => void;
    setSectionDirtyState: (section: ConversationSettingsSection, hasChanges: boolean, isValid?: boolean) => void;
    syncConfigurationActionState: () => void;
}

const createConversationSettingsControllerBundle = (inputArguments: ConversationSettingsControllerRegistryArguments): ConversationSettingsControllerBundle => {
    const workspacePathController = new ConversationWorkspacePathSettingsController({
        host: inputArguments.host,
        onDirtyStateChange: (hasChanges) => inputArguments.setSectionDirtyState('workspace', hasChanges)
    });

    const chatApi = requireConversationSettingsChatApi(inputArguments.host);
    const ragController = new RagConversationSettingsController({
        host: inputArguments.host,
        api: chatApi.rag,
        callbacks: {
            updateSectionApplyState: ({ baseline, current, hasChanges, isValid }) =>
                applyConversationSectionApplyState({
                    baseline,
                    current,
                    hasChanges,
                    section: 'rag',
                    sectionState: inputArguments.readSectionState(),
                    resolveSectionApplyStateTransition,
                    isValid,
                    setSectionState: (state) => {
                        inputArguments.writeSectionState(state);
                    },
                    syncConfigurationActionState: inputArguments.syncConfigurationActionState
                }),
            onBaselineConfigChange: (config) => {
                const previousEnabled = inputArguments.readState().ragConfig?.enabled === true;
                inputArguments.writeRagConfig(config);
                if (inputArguments.readState().mcpConfig && previousEnabled !== (config?.enabled === true)) {
                    inputArguments.refreshKnowledgeManagedMcpState();
                }
            },
            applyConfigUpdates: async (options) =>
                applyConversationSettingsUpdate({
                    ...options,
                    updateToken: options.updateToken(),
                    isStillActive: () => options.conversationId === inputArguments.readState().conversationId,
                    runWithBoundary: (boundary, request) => inputArguments.host.workflow.runWithBoundary(boundary, request),
                    showNotification: (message, type) => inputArguments.host.workflow.showNotification(message, type)
                }),
            onDirtyStateChange: (hasChanges) => inputArguments.setSectionDirtyState('rag', hasChanges)
        }
    });
    ragController.setConversation(inputArguments.readConversationId(), inputArguments.readLoadToken());

    const mcpController = new McpConversationSettingsController({
        host: inputArguments.host,
        readConversationId: inputArguments.readConversationId,
        readMcpConfig: () => inputArguments.readState().mcpConfig,
        writeMcpConfig: (config) => {
            inputArguments.writeMcpConfig(config);
        },
        readMcpTools: () => inputArguments.readState().mcpTools,
        writeMcpTools: (tools) => {
            inputArguments.writeMcpTools(tools);
        },
        readMcpCanonicalToolDefaults: () => inputArguments.readState().mcpCanonicalToolDefaults,
        writeMcpCanonicalToolDefaults: (defaults) => {
            inputArguments.writeMcpCanonicalToolDefaults(defaults);
        },
        onDirtyStateChange: (hasChanges) => inputArguments.setSectionDirtyState('mcp', hasChanges)
    });

    const identityPromptsController = new IdentityPromptsConversationSettingsController({
        host: inputArguments.host,
        onDirtyStateChange: (hasChanges) => inputArguments.setSectionDirtyState('identityPrompts', hasChanges)
    });

    return {
        workspacePathController,
        identityPromptsController,
        mcpController,
        ragController
    };
};

const bindConversationSettingsControllerEvents = (bundle: ConversationSettingsControllerBundle, modal: HTMLElement, defaultToolsModal: HTMLElement): Array<() => void> => {
    return [...bundle.workspacePathController.bindEvents(modal), ...bundle.ragController.bindEvents(modal), ...bundle.mcpController.bindEvents(modal, defaultToolsModal), ...bundle.identityPromptsController.bindEvents(modal)];
};

const disposeConversationSettingsControllerBundle = (bundle: ConversationSettingsControllerBundle | null): void => {
    if (!bundle) {
        return;
    }
    bundle.workspacePathController.dispose();
    bundle.ragController.dispose();
    bundle.mcpController.dispose();
    bundle.identityPromptsController.dispose();
};

const disposeConversationSettingsBindings = (disposers: Array<() => void>): void => {
    runDisposerCallbacks(disposers);
};

export { bindConversationSettingsControllerEvents, createConversationSettingsControllerBundle, disposeConversationSettingsBindings, disposeConversationSettingsControllerBundle };
export type { ConversationSettingsControllerBundle, ConversationSettingsControllerRegistryArguments };

/* SoAI - Chat feature conversation settings manager [frontend/assets/ts/features/chat/conversationsettings/ChatConversationSettingsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { canInteractivelyAdjustConversationTools, isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { resolveConversationSectionStateTransition } from '@features/chat/conversationsettings/actions.ts';
import { syncAgentModeMcpToolsEnabledState } from '@features/chat/conversationsettings/agentModeMcpSync.ts';
import { applyManagedModalVisibility } from '@features/chat/conversationsettings/managedModalVisibility.ts';
import { openConversationSettings } from '@features/chat/conversationsettings/configurationOpenFlow.ts';
import { bindConversationSettingsControllerEvents, createConversationSettingsControllerBundle, disposeConversationSettingsBindings, disposeConversationSettingsControllerBundle, type ConversationSettingsControllerBundle } from '@features/chat/conversationsettings/controllerRegistry.ts';
import { clearConversationSettingsHydration } from '@features/chat/conversationsettings/conversationSettingsLoading.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { createDefaultState, type SettingsState } from '@features/chat/conversationsettings/settingsModels.ts';
import { createDefaultSectionState } from '@features/chat/conversationsettings/sectionState.ts';
import type { ChatConversationSettingsManagerDependencies, ConversationSettingsSection, ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import { reconcileMcpIntentAfterKnowledge } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/mcpPresetStaging.ts';
import type { ChatPresetSections } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';

class ChatConversationSettingsManager {
    readonly host: ConversationSettingsHost;
    #controllers: ConversationSettingsControllerBundle | null = null;
    #modal: Element | null = null;
    #defaultToolsModal: Element | null = null;
    #disposers: Array<() => void> = [];
    #eventsBound = false;
    #loadToken = new SequenceToken();
    #hydrationOperation: Promise<void> = Promise.resolve();
    #sectionState: ConversationSettingsSectionState = createDefaultSectionState();
    #state: SettingsState = createDefaultState();

    constructor(dependencies: ChatConversationSettingsManagerDependencies) {
        this.host = dependencies.host;
    }

    dispose(): void {
        disposeConversationSettingsControllerBundle(this.#controllers);
        this.#controllers = null;
        disposeConversationSettingsBindings(this.#disposers);
        this.#disposers = [];
        this.#eventsBound = false;
        this.#modal = null;
        this.#defaultToolsModal = null;
    }

    handleConfigurationOpen(): void {
        this.#ensureEventsBound();
        const controllers = this.#requireControllers();
        this.#applyManagedModalVisibility();
        const hydrationOperation = openConversationSettings({
            host: this.host,
            controllers,
            modal: this.#modal,
            defaultToolsModal: this.#defaultToolsModal,
            readConversationId: () => this.#state.conversationId,
            resetState: (conversationId) => this.#resetState(conversationId),
            nextLoadToken: () => this.#loadToken.next(),
            isLoadTokenActive: (token) => this.#loadToken.isActive(token),
            isIdentityPromptsDirty: () => this.#sectionState.identityPromptsDirty,
            writeSearchConfig: (config) => {
                this.#state.searchConfig = config;
            },
            writeWorkspacePathConfig: (config) => {
                this.#state.workspacePathConfig = config;
            }
        });
        this.#hydrationOperation = hydrationOperation.then(
            () => undefined,
            () => undefined
        );
    }

    handleConfigurationClose(): void {
        this.#loadToken.invalidate();
        clearConversationSettingsHydration({ containers: [this.#modal, this.#defaultToolsModal].filter((element): element is Element => element !== null) });
        const controllers = this.#controllers;
        controllers?.workspacePathController.resetUI();
        this.host.workflow.setConversationSettingsSavePlan(null);
    }

    handleConfigurationTabChange(tabId: string): void {
        if (!tabId) {
            return;
        }
        this.#syncConfigurationActionState();
    }

    handleModelStreamUpdate(models: readonly ModelData[] | null | undefined): void {
        this.#controllers?.ragController.handleModelStreamUpdate(models);
    }

    handleCurrentConversationToolsLockStateChange(): void {
        const conversation = this.host.data.getCurrentConversation();
        if (!this.#modal || this.#modal.classList.contains('u-hidden') || !this.#state.mcpConfig || !canInteractivelyAdjustConversationTools(conversation) || conversation.id !== this.#state.conversationId) {
            return;
        }
        const hasChanges = syncAgentModeMcpToolsEnabledState({
            host: this.host,
            modalRoot: this.#modal,
            defaultToolsModalRoot: this.#defaultToolsModal,
            config: this.#state.mcpConfig,
            writeMcpConfig: (config) => {
                this.#state.mcpConfig = config;
            }
        });
        this.#setSectionDirtyState('mcp', hasChanges);
    }

    handleConversationSwitch(conversationId: string | null): void {
        const conversation = this.host.data.getCurrentConversation();
        const interactiveConversationId = canInteractivelyAdjustConversationTools(conversation) && conversation.id === conversationId ? conversationId : null;
        if (this.#state.conversationId === interactiveConversationId) {
            return;
        }
        this.#resetState(interactiveConversationId);
        if (this.#modal && !this.#modal.classList.contains('u-hidden')) {
            this.handleConfigurationOpen();
        }
    }

    handleConversationDeleted(conversationId: string): void {
        if (this.#state.conversationId === conversationId) {
            this.#resetState(null);
        }
    }

    handleMcpDefaultToolsModalOpen(): void {
        this.#ensureEventsBound();
        this.#requireControllers().mcpController.handleDefaultToolsModalOpen();
    }

    presetControllers(): ConversationSettingsControllerBundle {
        this.#ensureEventsBound();
        return this.#requireControllers();
    }

    stageToolParameterDefaults(parameters: Pick<ChatParameters, 'toolsEnabled' | 'toolApprovalRequired'>): boolean {
        const controller = this.#controllers?.mcpController;
        const workingValues = controller?.workingValues() ?? null;
        if (!controller || !workingValues || !controller.isHydrated() || !controller.isEditable()) {
            return false;
        }
        controller.commitWorkingValues({
            ...workingValues,
            toolsEnabled: parameters.toolsEnabled === true,
            toolApprovalRequired: parameters.toolApprovalRequired === true
        });
        controller.refreshWorkingPresentation();
        return true;
    }

    awaitPresetHydration(sections: ChatPresetSections): Promise<void> {
        const requiresSettingsHydration = sections.files !== undefined || sections.knowledge !== undefined || sections.tools !== undefined;
        const settingsHydration = requiresSettingsHydration ? this.#hydrationOperation : Promise.resolve();
        const requiresModelHydration = typeof sections.general?.['model'] === 'string' || sections.voice !== undefined;
        const modelHydration = requiresModelHydration ? this.host.workflow.runWithBoundary('chat:presetModelCatalog', () => this.host.workflow.ensureModelStream()) : Promise.resolve();
        return Promise.all([settingsHydration, modelHydration]).then(async () => {
            if (typeof sections.knowledge?.['embedding_model'] === 'string') await this.#requireControllers().ragController.awaitEmbeddingModelHydration();
        });
    }

    conversationMutationPatch(): ConversationModelSettingsUpdate {
        const controllers = this.#requireControllers();
        return {
            ...controllers.identityPromptsController.conversationPatch(),
            ...controllers.workspacePathController.conversationPatch()
        };
    }

    #resetState(conversationId: string | null): void {
        this.#loadToken.invalidate();
        this.#state = createDefaultState(conversationId);
        this.#sectionState = createDefaultSectionState();
        const controllers = this.#controllers;
        if (!controllers) {
            this.#syncConfigurationActionState();
            return;
        }
        controllers.workspacePathController.setConversation(conversationId);
        if (this.#eventsBound) {
            controllers.workspacePathController.resetUI();
        }
        if (this.#eventsBound) {
            controllers.identityPromptsController.resetUI();
        }
        controllers.ragController.setConversation(conversationId, this.#loadToken.value);
        if (this.#eventsBound) {
            controllers.ragController.resetUI();
            controllers.mcpController.resetUI();
        }
        this.#syncConfigurationActionState();
    }

    #ensureEventsBound(): void {
        if (this.#eventsBound) {
            return;
        }
        if (!this.#controllers) {
            this.#controllers = createConversationSettingsControllerBundle({
                host: this.host,
                readConversationId: () => this.#state.conversationId,
                readLoadToken: () => this.#loadToken.value,
                readSectionState: () => this.#sectionState,
                writeSectionState: (state) => {
                    this.#sectionState = state;
                },
                readState: () => this.#state,
                writeRagConfig: (config) => {
                    this.#state.ragConfig = config;
                },
                writeMcpConfig: (config) => {
                    this.#state.mcpConfig = config;
                },
                writeMcpTools: (tools) => {
                    this.#state.mcpTools = tools;
                },
                writeMcpCanonicalToolDefaults: (defaults) => {
                    this.#state.mcpCanonicalToolDefaults = defaults;
                },
                refreshKnowledgeManagedMcpState: () => this.#refreshKnowledgeManagedMcpState(),
                setSectionDirtyState: (section, hasChanges) => this.#setSectionDirtyState(section, hasChanges),
                syncConfigurationActionState: () => this.#syncConfigurationActionState()
            });
        }
        const modal = requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID);
        const defaultToolsModal = requireModalPresenter().requireElement(CHAT_MCP_DEFAULT_TOOLS_MODAL_ID);
        this.#modal = modal;
        this.#defaultToolsModal = defaultToolsModal;
        this.#eventsBound = true;
        this.#disposers.push(...bindConversationSettingsControllerEvents(this.#controllers, modal, defaultToolsModal));
    }

    #requireControllers(): ConversationSettingsControllerBundle {
        if (!this.#controllers) {
            throw new Error('Chat conversation settings require controller initialization');
        }
        return this.#controllers;
    }

    #syncConfigurationActionState(): void {
        const controllers = this.#controllers;
        const presentationToken = this.#loadToken.value;
        const isPresentationActive = (): boolean => this.#loadToken.isActive(presentationToken);
        const identityDirty = this.#sectionState.identityPromptsDirty;
        const workspaceDirty = this.#sectionState.workspaceDirty;
        const knowledgeDirty = this.#sectionState.ragDirty;
        const ragIntent = controllers?.ragController.workingConfig() ?? null;
        const ragOperation = controllers?.ragController.prepareConfigApply(ragIntent, isPresentationActive) ?? null;
        const capturedConversation = this.host.data.getCurrentConversation();
        const workspaceOperation = workspaceDirty && controllers ? controllers.workspacePathController.prepareConversationSave(isPresentationActive) : null;
        const mcpIntent = controllers?.mcpController.workingValues() ?? null;
        const mcpBaseline = controllers?.mcpController.baselineConfig() ?? null;
        const mcpConversationId = this.#state.conversationId;
        const mcpAcceptedWritable = mcpConversationId !== null && capturedConversation?.id === mcpConversationId && isChatConversationSettingsWritable(capturedConversation);
        const mcpOperation = controllers?.mcpController.prepareConfigApply(mcpIntent, mcpBaseline, mcpConversationId, isPresentationActive, mcpAcceptedWritable) ?? null;
        this.host.workflow.setConversationSettingsSavePlan({
            conversation:
                identityDirty || workspaceDirty
                    ? {
                          hasChanges: true,
                          isValid: controllers?.identityPromptsController.isValid() !== false && controllers?.workspacePathController.isValid() !== false,
                          handler: async () => {
                              if (!controllers) return;
                              if (identityDirty && isPresentationActive() && this.host.data.getCurrentConversation() === capturedConversation) controllers.identityPromptsController.finalizeConversationSave();
                              if (workspaceOperation && !(await workspaceOperation())) return { type: 'continue-degraded' };
                              return;
                          }
                      }
                    : null,
            knowledge: knowledgeDirty ? { hasChanges: true, isValid: this.#sectionState.ragValid, handler: ragOperation ? async () => ((await ragOperation()) ? undefined : { type: 'continue-degraded' }) : null } : null,
            tools: this.#sectionState.mcpDirty
                ? {
                      hasChanges: true,
                      isValid: true,
                      handler: controllers
                          ? async () => {
                                let intent = mcpIntent;
                                let skipped = 0;
                                let degraded = false;
                                if (knowledgeDirty && intent && mcpBaseline) {
                                    const refreshed = await controllers.mcpController.refreshKnowledgeManagedState(mcpConversationId);
                                    const reconciled = reconcileMcpIntentAfterKnowledge(intent, mcpBaseline, refreshed.config, refreshed.tools);
                                    intent = reconciled.values;
                                    skipped = reconciled.skippedValues.length;
                                    degraded = !(await controllers.mcpController.prepareConfigApply(intent, refreshed.config, mcpConversationId, isPresentationActive, mcpAcceptedWritable)());
                                } else {
                                    degraded = Boolean(mcpOperation && !(await mcpOperation()));
                                }
                                return skipped > 0 || degraded ? { type: 'continue-degraded' } : undefined;
                            }
                          : null
                  }
                : null
        });
    }

    #applyManagedModalVisibility(): void {
        if (!this.#modal) {
            return;
        }
        applyManagedModalVisibility(this.host, this.#modal, this.host.data.getCurrentConversation());
    }

    #refreshKnowledgeManagedMcpState(): void {
        if (!this.#eventsBound || !this.#modal || this.#modal.classList.contains('u-hidden')) {
            return;
        }
        const controllers = this.#controllers;
        if (!controllers) {
            return;
        }
        terminateHandledPromise(controllers.mcpController.refreshKnowledgeManagedState());
    }

    #setSectionDirtyState(section: ConversationSettingsSection, hasChanges: boolean, isValid = true): void {
        const transition = resolveConversationSectionStateTransition(this.#sectionState, section, hasChanges, isValid);
        if (!transition.changed) {
            return;
        }
        this.#sectionState = transition.state;
        this.#syncConfigurationActionState();
    }
}

export { ChatConversationSettingsManager };

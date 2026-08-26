/* SoAI - MCP conversation settings service [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { clearMcpToolChangeSurfaces, normalizeMcpConfigValues } from '@core/mcp/toolChangeSurfaces.ts';
import { applyMcpToolGroupToggle } from '@core/mcp/toolGroupToggle.ts';
import { filterMcpToolGroupTools } from '@core/mcp/toolSearchFilter.ts';
import { buildMcpToggleSwitch, openDefaultToolsModal, readExpandedToolGroupIds, updateToggleState } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/dom.ts';
import { bindMcpConversationSettingsEvents } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/events.ts';
import { applyMcpLoadResult, syncMcpChangeSurfaces } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/effects.ts';
import { applyDefaultToolsToggleChange, applyToolModeReset, applyToolModeTabChange, hasMcpConfigChanges, resolveInitialToolTab, resolveMcpConfigSnapshot } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actions.ts';
import { applyServerToolAvailability, readMcpFormValues, readServerConfigMap } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/state.ts';
import { renderConfig, renderDefaultToolsModal, renderDefaultToolsSummary, resetMcpUi } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/view.ts';
import type { McpConversationSettingsControllerDependencies } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/types.ts';
import type { McpConfig, McpFormValues, McpTool, McpToolMode } from '@features/chat/conversationsettings/settingsModels.ts';
import type { ConversationMcpConfigResponse, ConversationMcpToolCatalogResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { canInteractivelyAdjustConversationTools, isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { prepareMcpConfigApply } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/preparedConfigApply.ts';
import { loadMcpKnowledgeManagedState, type McpKnowledgeState } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/knowledgeStateRefresh.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';

class McpConversationSettingsController {
    readonly #dependencies: McpConversationSettingsControllerDependencies;
    #updateToken = new SequenceToken();
    #refreshToken = new SequenceToken();
    #modal: Element | null = null;
    #defaultToolsModal: Element | null = null;
    #eventsAbortController: AbortController | null = null;
    #activeToolTab: McpToolMode = 'default';
    #expandedToolGroupIds = new Set<string>();
    #workingValues: McpFormValues | null = null;
    #catalogHydrated = false;
    #projectionConfig: McpConfig | null = null;

    constructor(dependencies: McpConversationSettingsControllerDependencies) {
        this.#dependencies = dependencies;
    }

    bindEvents(modal: HTMLElement, defaultToolsModal: HTMLElement): Array<() => void> {
        this.#modal = modal;
        this.#defaultToolsModal = defaultToolsModal;
        this.#eventsAbortController?.abort('chat-mcp-events-rebind');
        const eventsAbortController = new AbortController();
        this.#eventsAbortController = eventsAbortController;
        const host = this.#dependencies.host;
        bindMcpConversationSettingsEvents({
            signal: eventsAbortController.signal,
            modal,
            defaultToolsModal,
            handlers: {
                onAutoToggleChange: (toggleElement) => {
                    updateToggleState(toggleElement);
                    this.#updateApplyState();
                },
                onServerToggleChange: (toggleElement) => {
                    updateToggleState(toggleElement);
                    applyServerToolAvailability(host, this.#modal, readServerConfigMap(host, this.#modal));
                    this.#updateApplyState();
                },
                onToolToggleChange: (toggleElement) => {
                    updateToggleState(toggleElement);
                    this.#updateApplyState();
                },
                onToolModeTabClick: (tabElement) =>
                    applyToolModeTabChange({
                        host: this.#dependencies.host,
                        tabElement,
                        activeToolTab: this.#activeToolTab,
                        setActiveToolTab: (mode: McpToolMode) => {
                            this.#activeToolTab = mode;
                        },
                        readMcpConfig: () => this.#dependencies.readMcpConfig(),
                        readFormValues: () => this.#readFormValues(),
                        renderConfig: (config: McpConfig) => this.#renderConfig(config),
                        handleDefaultToolsModalOpen: () => this.handleDefaultToolsModalOpen(),
                        updateApplyState: () => this.#updateApplyState()
                    }),
                onToolGroupToggleClick: (toggleElement) => {
                    const result = applyMcpToolGroupToggle(toggleElement);
                    if (result.expanded) {
                        this.#expandedToolGroupIds.add(result.serverId);
                    } else {
                        this.#expandedToolGroupIds.delete(result.serverId);
                    }
                },
                onDefaultToolsTriggerClick: () => openDefaultToolsModal(),
                onDefaultToolsToggleChange: (toggleElement) =>
                    applyDefaultToolsToggleChange({
                        host,
                        element: toggleElement,
                        activeToolTab: this.#activeToolTab,
                        modalRoot: this.#modal,
                        defaultToolsModalRoot: this.#defaultToolsModal,
                        readMcpConfig: () => this.#dependencies.readMcpConfig(),
                        readFormValues: () => this.#readFormValues(),
                        updateApplyState: () => this.#updateApplyState()
                    }),
                onToolModeResetClick: () =>
                    applyToolModeReset({
                        host,
                        activeToolTab: this.#activeToolTab,
                        modalRoot: this.#modal,
                        defaultToolsModalRoot: this.#defaultToolsModal,
                        canonicalToolDefaults: this.#dependencies.readMcpCanonicalToolDefaults(),
                        applyServerToolAvailability: (serverConfigs: Record<string, boolean>) => applyServerToolAvailability(host, this.#modal, serverConfigs),
                        readFormValues: () => this.#readFormValues(),
                        updateApplyState: () => this.#updateApplyState()
                    }),
                onToolSearchInput: (inputElement) => filterMcpToolGroupTools(inputElement)
            }
        });
        return [
            (): void => {
                eventsAbortController.abort('chat-mcp-events-dispose');
                if (this.#eventsAbortController === eventsAbortController) {
                    this.#eventsAbortController = null;
                }
            }
        ];
    }

    resetUI(): void {
        this.#workingValues = null;
        this.#catalogHydrated = false;
        this.#projectionConfig = null;
        resetMcpUi(
            this.#dependencies.host,
            this.#modal,
            this.#defaultToolsModal,
            (hasChanges: boolean) => this.#dependencies.onDirtyStateChange(hasChanges),
            () => this.#renderSummary()
        );
        clearMcpToolChangeSurfaces(this.#modal, this.#defaultToolsModal);
    }

    handleDefaultToolsModalOpen(): void {
        const config = resolveMcpConfigSnapshot(this.#dependencies.readMcpConfig(), this.#readFormValues());
        if (!config) {
            return;
        }
        renderDefaultToolsModal({
            host: this.#dependencies.host,
            defaultToolsModalRoot: this.#defaultToolsModal,
            config,
            tools: this.#dependencies.readMcpTools(),
            activeToolTab: this.#activeToolTab,
            canonicalToolDefaults: this.#dependencies.readMcpCanonicalToolDefaults(),
            buildToggleSwitch: buildMcpToggleSwitch,
            expandedToolGroupIds: readExpandedToolGroupIds(this.#defaultToolsModal)
        });
        syncMcpChangeSurfaces({ modalRoot: this.#modal, defaultToolsModalRoot: this.#defaultToolsModal, baseline: this.#dependencies.readMcpConfig(), current: this.#readFormValues() });
    }

    applyLoadResult(configResult: PromiseSettledResult<ConversationMcpConfigResponse>, toolsResult: PromiseSettledResult<ConversationMcpToolCatalogResponse>): void {
        applyMcpLoadResult({
            host: this.#dependencies.host,
            conversationId: this.#dependencies.readConversationId(),
            configResult,
            toolsResult,
            writeMcpConfig: (config: McpConfig | null) => this.#dependencies.writeMcpConfig(config),
            writeMcpTools: (tools: McpTool[]) => this.#dependencies.writeMcpTools(tools),
            writeMcpCanonicalToolDefaults: (defaults) => this.#dependencies.writeMcpCanonicalToolDefaults(defaults)
        });
        this.#catalogHydrated = toolsResult.status === 'fulfilled';
        this.#expandedToolGroupIds.clear();
        this.#activeToolTab = resolveInitialToolTab(this.#dependencies.host.data.getCurrentConversation());
        const config = this.#dependencies.readMcpConfig();
        if (!config) {
            this.resetUI();
            return;
        }
        this.#workingValues = normalizeMcpConfigValues(config);
        this.#projectionConfig = null;
        this.#renderConfig(config);
        this.handleDefaultToolsModalOpen();
        this.#updateApplyState();
    }

    async refreshKnowledgeManagedState(capturedConversationId: string | null = this.#dependencies.readConversationId()): Promise<McpKnowledgeState> {
        if (!capturedConversationId) {
            throw new Error('Authoritative MCP refresh requires a conversation.');
        }
        const refreshToken = this.#refreshToken.next();
        const result = await loadMcpKnowledgeManagedState(this.#dependencies.host, capturedConversationId);
        const snapshot = { config: result.config, tools: result.tools };
        if (!this.#refreshToken.isActive(refreshToken)) {
            return snapshot;
        }
        if (capturedConversationId !== this.#dependencies.readConversationId()) {
            return snapshot;
        }
        if (!this.#modal || this.#modal.classList.contains('u-hidden')) {
            return snapshot;
        }
        this.applyLoadResult(result.configResult, result.toolsResult);
        return snapshot;
    }

    prepareConfigApply(capturedValues: McpFormValues | null = null, capturedBaseline: McpConfig | null = this.#dependencies.readMcpConfig(), capturedConversationId: string | null = this.#dependencies.readConversationId(), isPresentationActive: () => boolean = () => true, acceptedWritableOverride: boolean | null = null): () => Promise<boolean> {
        const currentValues = capturedValues ?? this.#workingValues ?? this.#readFormValues();
        const capturedConversation = this.#dependencies.host.data.getCurrentConversation();
        const acceptedWritable = acceptedWritableOverride ?? (capturedConversationId !== null && capturedConversation?.id === capturedConversationId && isChatConversationSettingsWritable(capturedConversation));
        return prepareMcpConfigApply({
            host: this.#dependencies.host,
            conversationId: capturedConversationId,
            baselineConfig: capturedBaseline,
            currentValues,
            acceptedWritable,
            canonicalToolDefaults: this.#dependencies.readMcpCanonicalToolDefaults(),
            nextUpdateToken: () => this.#updateToken.next(),
            isUpdateTokenActive: (updateToken: number, activeConversationId: string) => this.#updateToken.isActive(updateToken) && activeConversationId === this.#dependencies.readConversationId() && isPresentationActive(),
            writeMcpConfig: (config: McpConfig | null) => this.#dependencies.writeMcpConfig(config),
            readMcpTools: () => this.#dependencies.readMcpTools(),
            renderConfig: (config: McpConfig) => this.#renderConfig(config),
            onNoChanges: () => {
                if (isPresentationActive()) this.#updateApplyState();
            },
            onActiveUpdateComplete: (config, reconciled) => this.#settleProjection(config, reconciled),
            projectDefaults: this.#dependencies.host.workflow.prepareMcpDefaultsProjection(),
            publishInvalidation: requireStorageService().prepareChatPreferenceInvalidation(),
            projectionConfig: this.#projectionConfig,
            settleProjection: (config, reconciled) => this.#settleProjection(config, reconciled)
        });
    }

    #readFormValues(): McpFormValues | null {
        return readMcpFormValues(this.#dependencies.host, this.#modal, this.#dependencies.readMcpConfig());
    }

    isHydrated(): boolean {
        return this.#dependencies.readMcpConfig() !== null && this.#workingValues !== null && this.#catalogHydrated;
    }

    isEditable(): boolean {
        const conversationId = this.#dependencies.readConversationId();
        const conversation = this.#dependencies.host.data.getCurrentConversation();
        return conversationId !== null && conversation?.id === conversationId && !isConversationAuthorityLocked(conversation) && (this.#projectionConfig !== null || canInteractivelyAdjustConversationTools(conversation));
    }

    workingValues(): McpFormValues | null {
        const values = this.#workingValues;
        return values ? { ...values, defaultTools: [...values.defaultTools], planTools: [...values.planTools], executeTools: [...values.executeTools], serverConfigs: { ...values.serverConfigs } } : null;
    }

    baselineConfig(): McpConfig | null {
        const config = this.#dependencies.readMcpConfig();
        return config ? { ...config, defaultTools: [...config.defaultTools], planTools: [...config.planTools], executeTools: [...config.executeTools], serverConfigs: { ...config.serverConfigs } } : null;
    }

    tools(): McpTool[] {
        return this.#dependencies.readMcpTools().map((tool) => ({ ...tool, icons: [...tool.icons] }));
    }

    commitWorkingValues(values: McpFormValues): void {
        this.#workingValues = { ...values, defaultTools: [...values.defaultTools], planTools: [...values.planTools], executeTools: [...values.executeTools], serverConfigs: { ...values.serverConfigs } };
    }

    refreshWorkingPresentation(): void {
        const baseline = this.#dependencies.readMcpConfig();
        const values = this.#workingValues;
        const snapshot = resolveMcpConfigSnapshot(baseline, values);
        if (!snapshot) {
            return;
        }
        this.#renderConfig(snapshot);
        this.handleDefaultToolsModalOpen();
        this.#updateApplyState();
    }

    #renderConfig(config: McpConfig): void {
        renderConfig({
            host: this.#dependencies.host,
            modalRoot: this.#modal,
            config,
            tools: this.#dependencies.readMcpTools(),
            activeToolTab: this.#activeToolTab,
            canonicalToolDefaults: this.#dependencies.readMcpCanonicalToolDefaults(),
            buildToggleSwitch: buildMcpToggleSwitch,
            applyServerToolAvailability: (serverConfigs: Record<string, boolean>) => applyServerToolAvailability(this.#dependencies.host, this.#modal, serverConfigs),
            renderDefaultToolsSummary: () => this.#renderSummary(),
            expandedToolGroupIds: this.#expandedToolGroupIds
        });
    }

    #renderSummary(): void {
        renderDefaultToolsSummary({
            host: this.#dependencies.host,
            modalRoot: this.#modal,
            config: resolveMcpConfigSnapshot(this.#dependencies.readMcpConfig(), this.#readFormValues()),
            tools: this.#dependencies.readMcpTools(),
            activeToolTab: this.#activeToolTab
        });
    }

    #settleProjection(config: McpConfig, reconciled: boolean): void {
        this.#workingValues = normalizeMcpConfigValues(config);
        this.#projectionConfig = reconciled ? null : config;
        if (reconciled) this.#updateApplyState();
        else this.#dependencies.onDirtyStateChange(true);
    }

    #updateApplyState(): void {
        this.#renderSummary();
        const baseline = this.#dependencies.readMcpConfig();
        const currentValues = this.#readFormValues();
        this.#workingValues = currentValues ? { ...currentValues, defaultTools: [...currentValues.defaultTools], planTools: [...currentValues.planTools], executeTools: [...currentValues.executeTools], serverConfigs: { ...currentValues.serverConfigs } } : null;
        if (!baseline || !currentValues) {
            this.#dependencies.onDirtyStateChange(false);
            syncMcpChangeSurfaces({ modalRoot: this.#modal, defaultToolsModalRoot: this.#defaultToolsModal, baseline: null, current: currentValues });
            return;
        }
        this.#dependencies.onDirtyStateChange(hasMcpConfigChanges(currentValues, baseline));
        syncMcpChangeSurfaces({ modalRoot: this.#modal, defaultToolsModalRoot: this.#defaultToolsModal, baseline, current: currentValues });
    }

    dispose(): void {
        this.#eventsAbortController?.abort('chat-mcp-dispose');
        this.#eventsAbortController = null;
        this.#updateToken.invalidate();
        this.#refreshToken.invalidate();
        this.#projectionConfig = null;
        this.#modal = null;
        this.#defaultToolsModal = null;
    }
}

export { McpConversationSettingsController };

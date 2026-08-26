/* SoAI - MCP conversation settings effects [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { normalizeMcpConfigValues, syncMcpToolChangeSurfaces } from '@core/mcp/toolChangeSurfaces.ts';
import type { ConversationMcpConfigResponse, ConversationMcpConfigUpdateRequest, ConversationMcpToolCatalogResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { requireConversationSettingsChatApi, type ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { parseMcpCanonicalToolDefaults, parseMcpConfig, parseMcpTools } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import { buildMcpConfigUpdatePlan } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actions.ts';
import type { McpCanonicalToolDefaults, McpConfig, McpFormValues, McpTool } from '@features/chat/conversationsettings/settingsModels.ts';

interface ApplyMcpLoadResultOptions {
    host: ConversationSettingsHost;
    conversationId: string | null;
    configResult: PromiseSettledResult<ConversationMcpConfigResponse>;
    toolsResult: PromiseSettledResult<ConversationMcpToolCatalogResponse>;
    writeMcpConfig: (config: McpConfig | null) => void;
    writeMcpTools: (tools: McpTool[]) => void;
    writeMcpCanonicalToolDefaults: (defaults: McpCanonicalToolDefaults | null) => void;
}

interface ApplyMcpConfigUpdatesOptions {
    host: ConversationSettingsHost;
    conversationId: string;
    updates: ConversationMcpConfigUpdateRequest;
    isStillActive: () => boolean;
    writeMcpConfig: (config: McpConfig | null) => void;
    readMcpTools: () => McpTool[];
    renderConfig: (config: McpConfig, tools: McpTool[]) => void;
    projectDefaults: (config: McpConfig) => Promise<boolean>;
    publishInvalidation: () => void;
}

interface ReconcileCommittedMcpConfigOptions {
    host: ConversationSettingsHost;
    conversationId: string;
    config: McpConfig;
    isStillActive: () => boolean;
    writeMcpConfig: (config: McpConfig | null) => void;
    readMcpTools: () => McpTool[];
    renderConfig: (config: McpConfig, tools: McpTool[]) => void;
    projectDefaults: (config: McpConfig) => Promise<boolean>;
}

interface CommittedMcpConfigReconciliation {
    active: boolean;
    reconciled: boolean;
}

interface ExecuteMcpConfigApplyOptions {
    host: ConversationSettingsHost;
    conversationId: string;
    baselineConfig: McpConfig;
    currentValues: McpFormValues;
    acceptedWritable: boolean;
    canonicalToolDefaults: McpCanonicalToolDefaults | null;
    nextUpdateToken: () => number;
    isUpdateTokenActive: (updateToken: number, conversationId: string) => boolean;
    writeMcpConfig: (config: McpConfig | null) => void;
    readMcpTools: () => McpTool[];
    renderConfig: (config: McpConfig) => void;
    onNoChanges: () => void;
    onActiveUpdateComplete: (config: McpConfig, projectionReconciled: boolean) => void;
    projectDefaults: (config: McpConfig) => Promise<boolean>;
    publishInvalidation: () => void;
}

interface SyncMcpChangeSurfacesOptions {
    modalRoot: Element | null;
    defaultToolsModalRoot: Element | null;
    baseline: McpConfig | null;
    current: McpFormValues | null;
}

const showMcpLoadFailure = (host: ConversationSettingsHost): void => {
    host.workflow.showNotification(i18n.t('chat.configuration.notifications.mcpLoadFailed'), 'error');
};

const syncMcpChangeSurfaces = ({ modalRoot, defaultToolsModalRoot, baseline, current }: SyncMcpChangeSurfacesOptions): void => {
    syncMcpToolChangeSurfaces({
        modalRoot,
        defaultToolsModalRoot,
        baseline: baseline ? normalizeMcpConfigValues(baseline) : null,
        current,
        includeTopLevelSurfaces: true
    });
};

const canWriteMcpConversationSettings = (host: ConversationSettingsHost, conversationId: string): boolean => {
    const conversation = host.data.getCurrentConversation();
    return conversation?.id === conversationId && isChatConversationSettingsWritable(conversation);
};

const writeMcpConfigToWritableConversation = (host: ConversationSettingsHost, conversationId: string | null, config: McpConfig): void => {
    if (conversationId && canWriteMcpConversationSettings(host, conversationId)) {
        host.workflow.applyMcpConfigToConversationModelSettings(conversationId, config);
    }
};

const applyMcpLoadResult = ({ host, conversationId, configResult, toolsResult, writeMcpConfig, writeMcpTools, writeMcpCanonicalToolDefaults }: ApplyMcpLoadResultOptions): void => {
    if (configResult.status === 'fulfilled') {
        try {
            const config = parseMcpConfig(configResult.value);
            writeMcpConfig(config);
            writeMcpConfigToWritableConversation(host, conversationId, config);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatConversationSettings', 'Failed to parse MCP config', runtimeError);
            writeMcpConfig(null);
            showMcpLoadFailure(host);
        }
    } else {
        const runtimeReason = ensureError(configResult.reason);
        errorHandler.error('ChatConversationSettings', 'Failed to load MCP config', runtimeReason);
        writeMcpConfig(null);
        showMcpLoadFailure(host);
    }

    if (toolsResult.status === 'fulfilled') {
        try {
            writeMcpTools(parseMcpTools(toolsResult.value));
            writeMcpCanonicalToolDefaults(parseMcpCanonicalToolDefaults(toolsResult.value));
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatConversationSettings', 'Failed to parse MCP tools', runtimeError);
            writeMcpTools([]);
            writeMcpCanonicalToolDefaults(null);
            showMcpLoadFailure(host);
        }
    } else {
        const runtimeReason = ensureError(toolsResult.reason);
        errorHandler.error('ChatConversationSettings', 'Failed to load MCP tools', runtimeReason);
        writeMcpTools([]);
        writeMcpCanonicalToolDefaults(null);
        showMcpLoadFailure(host);
    }
};

const reconcileCommittedMcpConfig = async ({ host, conversationId, config, isStillActive, writeMcpConfig, readMcpTools, renderConfig, projectDefaults }: ReconcileCommittedMcpConfigOptions): Promise<CommittedMcpConfigReconciliation> => {
    let reconciled = true;
    try {
        reconciled = await projectDefaults(config);
    } catch (error) {
        reconciled = false;
        errorHandler.warn('ChatConversationSettings', 'MCP preference projection failed after commit', ensureError(error));
    }
    if (!isStillActive()) {
        return { active: false, reconciled };
    }
    writeMcpConfig(config);
    try {
        renderConfig(config, readMcpTools());
        writeMcpConfigToWritableConversation(host, conversationId, config);
        host.workflow.refreshTokenCounterPreview();
    } catch (error) {
        reconciled = false;
        errorHandler.warn('ChatConversationSettings', 'MCP presentation projection failed after commit', ensureError(error));
    }
    return { active: true, reconciled };
};

const applyMcpConfigUpdates = async ({ host, conversationId, updates, isStillActive, writeMcpConfig, readMcpTools, renderConfig, projectDefaults, publishInvalidation }: ApplyMcpConfigUpdatesOptions): Promise<Readonly<{ active: boolean; config: McpConfig | null; reconciled: boolean }>> => {
    const chatApi = requireConversationSettingsChatApi(host);
    const updated = await host.workflow.runWithBoundary('chat:mcpUpdate', () => chatApi.mcp.updateConfig(conversationId, updates));
    const updatedConfig = parseMcpConfig(updated);
    publishInvalidation();
    const reconciliation = await reconcileCommittedMcpConfig({ host, conversationId, config: updatedConfig, isStillActive, writeMcpConfig, readMcpTools, renderConfig, projectDefaults });
    return { ...reconciliation, config: updatedConfig };
};

const executeMcpConfigApply = async ({ host, conversationId, baselineConfig, currentValues, acceptedWritable, canonicalToolDefaults, nextUpdateToken, isUpdateTokenActive, writeMcpConfig, readMcpTools, renderConfig, onNoChanges, onActiveUpdateComplete, projectDefaults, publishInvalidation }: ExecuteMcpConfigApplyOptions): Promise<boolean> => {
    if (!acceptedWritable) {
        onNoChanges();
        return true;
    }
    const updatePlan = buildMcpConfigUpdatePlan(currentValues, baselineConfig, canonicalToolDefaults);
    if (Object.keys(updatePlan.updates).length === 0) {
        onNoChanges();
        return true;
    }

    const updateToken = nextUpdateToken();
    const isStillWritable = (): boolean => isUpdateTokenActive(updateToken, conversationId) && canWriteMcpConversationSettings(host, conversationId);
    const updated = await applyMcpConfigUpdates({
        host,
        conversationId,
        updates: updatePlan.updates,
        isStillActive: isStillWritable,
        writeMcpConfig,
        readMcpTools,
        renderConfig: (config: McpConfig, _tools: McpTool[]) => renderConfig(config),
        projectDefaults,
        publishInvalidation
    });
    if (updated.active && isStillWritable()) {
        if (updated.config) onActiveUpdateComplete(updated.config, updated.reconciled);
    }
    return updated.reconciled;
};
export { applyMcpLoadResult, executeMcpConfigApply, reconcileCommittedMcpConfig, syncMcpChangeSurfaces };
export type { ApplyMcpConfigUpdatesOptions, ApplyMcpLoadResultOptions, ExecuteMcpConfigApplyOptions, ReconcileCommittedMcpConfigOptions, SyncMcpChangeSurfacesOptions };

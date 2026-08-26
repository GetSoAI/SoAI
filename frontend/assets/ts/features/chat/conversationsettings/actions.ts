/* SoAI - Chat feature conversation settings actions [frontend/assets/ts/features/chat/conversationsettings/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID } from '@features/chat/modals/constants.ts';
import { requireConversationSettingsChatApi, type ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { beginConversationSettingsHydration, type ConversationSettingsHydrationSession } from '@features/chat/conversationsettings/conversationSettingsLoading.ts';
import { parseConversationWorkspacePathConfig, parseSearchConfig } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import { McpConversationSettingsController } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/service.ts';
import { RagConversationSettingsController } from '@features/chat/conversationsettings/ragconversationsettings/service/RagConversationSettingsController.ts';
import type { ConversationWorkspacePathConfig, SearchConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { ConversationSettingsActionState, ConversationSettingsSection, ConversationSettingsSectionActionHandlers, ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ConversationSearchConfigResponse, ConversationWorkspacePathConfigResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';

interface ConversationSettingsActionStateParameters {
    activeTab: string;
    sectionState: ConversationSettingsSectionState;
    sectionHandlers: ConversationSettingsSectionActionHandlers;
}

interface ConversationSettingsSectionStateTransition {
    changed: boolean;
    state: ConversationSettingsSectionState;
}

interface ConversationSettingsSectionApplyCheckResult<T> {
    baseline: T | null;
    current: T | null;
    hasChanges: (current: T, baseline: T) => boolean;
    isValid?: boolean | undefined;
    section: ConversationSettingsSection;
    sectionState: ConversationSettingsSectionState;
}

interface ConversationSettingsLoadArguments {
    conversation: Conversation;
    host: ConversationSettingsHost;
    loadToken: number;
    modal: Element | null;
    defaultToolsModal: Element | null;
    ragController: RagConversationSettingsController;
    mcpController: McpConversationSettingsController;
    onConversationPersisted?: (conversation: Conversation) => void;
    setSearchConfig: (config: SearchConfig | null) => void;
    setWorkspacePathConfig: (config: ConversationWorkspacePathConfig | null) => void;
    isLoadTokenActive: (loadToken: number) => boolean;
}

const resolveConversationSectionActionState = ({ activeTab, sectionState, sectionHandlers }: ConversationSettingsActionStateParameters): ConversationSettingsActionState => {
    if (!activeTab) {
        return null;
    }
    const applyRag = sectionState.ragDirty;
    const applyMcp = sectionState.mcpDirty;
    const applyIdentity = sectionState.identityPromptsDirty;
    const applyWorkspace = sectionState.workspaceDirty;
    if (!applyRag && !applyMcp && !applyIdentity && !applyWorkspace) {
        return null;
    }
    return {
        hasChanges: true,
        isValid: sectionState.ragValid,
        handler: async () => {
            if (applyIdentity) {
                await sectionHandlers.onApplyIdentityPromptsChanges();
            }
            if (applyMcp) {
                await sectionHandlers.onApplyMcpChanges();
            }
            if (applyRag) {
                await sectionHandlers.onApplyRagChanges();
            }
            if (applyWorkspace) {
                await sectionHandlers.onApplyWorkspaceChanges();
            }
        }
    };
};

const resolveConversationSectionStateTransition = (sectionState: ConversationSettingsSectionState, section: ConversationSettingsSection, hasChanges: boolean, isValid = true): ConversationSettingsSectionStateTransition => {
    if (section === 'rag' && sectionState.ragDirty === hasChanges && sectionState.ragValid === isValid) {
        return { changed: false, state: sectionState };
    }
    if (section === 'mcp' && sectionState.mcpDirty === hasChanges) {
        return { changed: false, state: sectionState };
    }
    if (section === 'identityPrompts' && sectionState.identityPromptsDirty === hasChanges) {
        return { changed: false, state: sectionState };
    }
    if (section === 'workspace' && sectionState.workspaceDirty === hasChanges) {
        return { changed: false, state: sectionState };
    }
    if (section === 'rag') {
        return { changed: true, state: { ...sectionState, ragDirty: hasChanges, ragValid: isValid } };
    }
    if (section === 'mcp') {
        return { changed: true, state: { ...sectionState, mcpDirty: hasChanges } };
    }
    if (section === 'identityPrompts') {
        return { changed: true, state: { ...sectionState, identityPromptsDirty: hasChanges } };
    }
    if (section === 'workspace') {
        return { changed: true, state: { ...sectionState, workspaceDirty: hasChanges } };
    }
    const exhaustive: never = section;
    throw new Error(`Unhandled chat conversation settings section: ${exhaustive}`);
};

const resolveSectionApplyStateTransition = <T>({ baseline, current, hasChanges, sectionState, section, isValid = true }: ConversationSettingsSectionApplyCheckResult<T>): ConversationSettingsSectionStateTransition => {
    if (!isValid) {
        return resolveConversationSectionStateTransition(sectionState, section, true, false);
    }
    if (!baseline || !current) {
        return resolveConversationSectionStateTransition(sectionState, section, false);
    }
    const changed = hasChanges(current, baseline);
    return resolveConversationSectionStateTransition(sectionState, section, changed);
};

const requireConversationSettingsElement = (modal: Element | null, selector: string): Element => {
    if (!modal) {
        throw new Error('Chat conversation settings require a modal root element');
    }
    const element = dom.resolve(selector, modal);
    if (!element) {
        throw new Error(`Chat conversation settings missing required element ${selector}`);
    }
    return element;
};

const requireConversationSettingsDefaultToolsModal = (defaultToolsModal: Element | null): Element => {
    if (!defaultToolsModal) {
        throw new Error('Chat conversation settings require a default tools modal root element');
    }
    return defaultToolsModal;
};

const parseSearchConfigLoadResult = (host: ConversationSettingsHost, result: PromiseSettledResult<ConversationSearchConfigResponse>): SearchConfig | null => {
    if (result.status !== 'fulfilled') {
        const runtimeReason = ensureError(result.reason);
        errorHandler.error('ChatConversationSettings', 'Failed to load web search config', runtimeReason);
        host.workflow.showNotification(i18n.t('chat.configuration.notifications.searchLoadFailed'), 'error');
        return null;
    }
    try {
        return parseSearchConfig(result.value);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatConversationSettings', 'Failed to parse web search config', runtimeError);
        host.workflow.showNotification(i18n.t('chat.configuration.notifications.searchLoadFailed'), 'error');
        return null;
    }
};

const parseWorkspacePathConfigLoadResult = (host: ConversationSettingsHost, result: PromiseSettledResult<ConversationWorkspacePathConfigResponse>): ConversationWorkspacePathConfig | null => {
    if (result.status !== 'fulfilled') {
        const runtimeReason = ensureError(result.reason);
        errorHandler.error('ChatConversationSettings', 'Failed to load conversation files folder config', runtimeReason);
        host.workflow.showNotification(i18n.t('chat.configuration.filesFolder.loadFailed'), 'error');
        return null;
    }
    try {
        return parseConversationWorkspacePathConfig(result.value);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatConversationSettings', 'Failed to parse conversation files folder config', runtimeError);
        host.workflow.showNotification(i18n.t('chat.configuration.filesFolder.loadFailed'), 'error');
        return null;
    }
};

const settleConversationSettingsRequest = async <T>(request: Promise<T>): Promise<PromiseSettledResult<T>> => {
    const results = await Promise.allSettled([request]);
    const result = results[0];
    if (!result) {
        throw new Error('Conversation settings request did not produce a settled result');
    }
    return result;
};

const loadConversationSettings = async (inputArguments: ConversationSettingsLoadArguments): Promise<void> => {
    const { conversation, host, loadToken, modal, defaultToolsModal, ragController, mcpController, setSearchConfig, isLoadTokenActive } = inputArguments;

    const conversationId = conversation.id;
    if (!conversationId) {
        return;
    }

    ragController.setConversation(conversationId, loadToken);

    const knowledgeContent = requireConversationSettingsElement(modal, modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'knowledge-content'));
    const mcpContent = requireConversationSettingsElement(modal, modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'mcp-content'));
    const selectedDefaultToolsModal = requireConversationSettingsDefaultToolsModal(defaultToolsModal);
    const defaultToolsBody = dom.resolve('.modal-body', selectedDefaultToolsModal);
    if (!defaultToolsBody) {
        throw new Error(`Chat conversation settings missing required element #${CHAT_MCP_DEFAULT_TOOLS_MODAL_ID} .modal-body`);
    }
    let hydrationSession: ConversationSettingsHydrationSession | null = beginConversationSettingsHydration({
        containers: [knowledgeContent, mcpContent, defaultToolsBody]
    });

    try {
        await host.workflow.runWithBoundary('chat:ensureConversationSettings', async () => {
            await host.data.conversationManager.ensureConversationPersisted(conversation);
        });
        if (!isLoadTokenActive(loadToken)) {
            hydrationSession.cancel();
            hydrationSession = null;
            return;
        }
        inputArguments.onConversationPersisted?.(conversation);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatConversationSettings', 'Failed to persist conversation before settings load', runtimeError);
        host.workflow.showNotification(i18n.t('chat.configuration.notifications.loadFailed'), 'error');
        hydrationSession?.cancel();
        hydrationSession = null;
        throw runtimeError;
    }

    const activeHydrationSession = hydrationSession;
    if (activeHydrationSession === null) {
        return;
    }

    try {
        const chatApi = requireConversationSettingsChatApi(host);
        terminateHandledPromise(ragController.loadEmbeddingModels(loadToken, conversationId));
        const ragConfigPromise = settleConversationSettingsRequest(chatApi.rag.getConfig(conversationId));
        const searchConfigPromise = settleConversationSettingsRequest(chatApi.search.getConfig(conversationId));
        const mcpConfigPromise = settleConversationSettingsRequest(chatApi.mcp.getConfig(conversationId));
        const mcpToolsPromise = settleConversationSettingsRequest(chatApi.mcp.getTools(conversationId));
        const workspaceConfigPromise = settleConversationSettingsRequest(host.data.api.webui.chat.workspacePath.getConfig(conversationId));
        const [ragConfigResult, searchConfigResult, mcpConfigResult, mcpToolsResult, workspaceConfigResult] = await Promise.all([ragConfigPromise, searchConfigPromise, mcpConfigPromise, mcpToolsPromise, workspaceConfigPromise]);

        if (!isLoadTokenActive(loadToken)) {
            return;
        }

        activeHydrationSession.releaseControlsBeforeRender();
        ragController.applyLoadResult(ragConfigResult);
        setSearchConfig(parseSearchConfigLoadResult(host, searchConfigResult));
        mcpController.applyLoadResult(mcpConfigResult, mcpToolsResult);
        inputArguments.setWorkspacePathConfig(parseWorkspacePathConfigLoadResult(host, workspaceConfigResult));
        activeHydrationSession.finish();
        hydrationSession = null;
    } finally {
        if (hydrationSession !== null) {
            activeHydrationSession.cancel();
        }
    }
};

export type { ConversationSettingsActionStateParameters, ConversationSettingsLoadArguments, ConversationSettingsSectionApplyCheckResult, ConversationSettingsSectionStateTransition };

export { loadConversationSettings, requireConversationSettingsDefaultToolsModal, requireConversationSettingsElement, resolveConversationSectionActionState, resolveConversationSectionStateTransition, resolveSectionApplyStateTransition };

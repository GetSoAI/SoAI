/* SoAI - Chat page adapters [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { CHAT_CONFIGURATION_MODAL_ID, ChatConversationManager, ChatParameterManager, isAgentModeRequiringTools } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import { initializeMessageManager } from '@pages/chat/controllers/chatpage/construction/initializers/messageManager.ts';
import { setCurrentConversationIdForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';

const initializeConversationManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.conversationRuntime.hasConversation()) {
        return;
    }
    page.runtime.conversationRuntime.initializeConversation(
        new ChatConversationManager(
            {
                api: page.platform.api,
                createConversationId: () => `conv_${generateSecureId()}`,
                onConversationPersisted: (conversationId) => page.sessions.composer.handleConversationPersisted(conversationId)
            },
            {
                conversations: page.state.conversationState.conversations,
                getCurrentConversationId: () => page.state.conversationState.currentConversationId,
                setCurrentConversationId: (conversationId) => {
                    setCurrentConversationIdForChatPage({ conversationState: page.state.conversationState, runtimeServices: page.state.runtimeServices, pageDom: page.page.pageDom, composer: page.sessions.composer, voiceSession: page.sessions.voiceSession }, conversationId);
                }
            }
        )
    );
};

const initializeParameterManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.configurationRuntime.hasParameters()) {
        return;
    }
    const configurationController = page.runtime.configurationRuntime.requireConfiguration();
    const configurationModalRoot = requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID);
    const dialogs = requireDialogsService();
    const isToolsParameterModeLocked = (): boolean => isAgentModeRequiringTools(page.sessions.conversationView.current()?.modelSettings);
    const isToolsParameterExecutionLocked = (): boolean => {
        const conversation = page.sessions.conversationView.current();
        return conversation?.id ? page.sessions.conversationView.isExecuting(conversation.id) : false;
    };
    page.runtime.configurationRuntime.initializeParameters(
        new ChatParameterManager({
            surface: {
                showConfirmation: (options) => dialogs.showConfirmation(options),
                showNotification: (message, type, duration) => page.page.feedback.show(message, type, duration),
                optionalUI: (selector, context) => page.page.pageDom.optional(selector, context ?? configurationModalRoot),
                queryUI: (selector) => page.page.pageDom.query(selector, configurationModalRoot),
                updateText: (element, text) => page.page.pageDom.updateText(element, text),
                updateProperty: (element, property, value) => page.page.pageDom.updateProperty(element, property, value),
                setUIValue: (element, value, options) => page.page.pageElements.setValue(element, value === null || value === undefined ? null : String(value), options),
                isEditingConfiguration: () => configurationController.isEditingConfiguration(),
                recalculateConfigurationDirtyState: () => configurationController.recalculateConfigurationDirtyState(),
                getWorkingParameters: () => configurationController.getWorkingParameters()
            },
            dom: { getData: (element, key) => page.platform.dom.getData(element, key) },
            hasParameterKey: (parameter) => parameter in page.state.settings.parameters,
            isParameterLocked: (parameter) => (parameter === 'toolsEnabled' && (isToolsParameterModeLocked() || isToolsParameterExecutionLocked())) || (parameter === 'agentMaxIterations' && isToolsParameterExecutionLocked()),
            resolveParameterLockHint: (parameter) => {
                if (parameter === 'toolsEnabled' && isToolsParameterModeLocked()) {
                    return 'chat.configuration.mcp.toolsEnabledLockedForAgentModeHint';
                }
                if (parameter === 'toolsEnabled' && isToolsParameterExecutionLocked()) {
                    return 'chat.configuration.mcp.toolsEnabledLockedWhileConversationRunningHint';
                }
                return null;
            },
            resolveParameterControlValue: (parameter, value) => (parameter === 'toolsEnabled' && isToolsParameterModeLocked() ? true : value),
            updateParameterValue: (parameter, value) => configurationController.updateParameterValue(parameter, value),
            setParameterValidity: (parameter, valid) => configurationController.setParameterValidity(parameter, valid),
            stageDefaultParameters: (parameters) => {
                const currentParameters = configurationController.getWorkingParameters();
                const coreParameters = {
                    ...parameters,
                    toolsEnabled: currentParameters.toolsEnabled,
                    toolApprovalRequired: currentParameters.toolApprovalRequired
                };
                configurationController.assignWorkingParameters(coreParameters);
                const settingsManager = page.runtime.configurationRuntime.optionalConversationSettings();
                const toolsStaged = settingsManager?.stageToolParameterDefaults(parameters) === true;
                return { skippedToolParameters: toolsStaged ? 0 : 2 };
            },
            getTextZoom: () => page.state.settings.textZoom,
            setTextZoom: (zoom) => {
                page.state.settings.textZoom = zoom;
            },
            getEditingTextZoom: () => configurationController.getEditingTextZoom(),
            setEditingTextZoom: (zoom) => configurationController.setEditingTextZoom(zoom),
            getTextZoomController: () => page.state.settings.textZoomController,
            applyTextZoom: () => page.state.settings.applyTextZoom(),
            savePreferences: () => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatParameterManager requires a storage manager');
                }
                page.runtime.conversationRuntime.requireStorage().savePreferences();
            }
        })
    );
};

export { initializeConversationManager, initializeMessageManager, initializeParameterManager };

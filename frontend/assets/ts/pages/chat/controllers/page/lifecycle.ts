/* SoAI - Chat page lifecycle [frontend/assets/ts/pages/chat/controllers/page/lifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchSystemLimits } from '@core/api/systemLimitsService.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { prepareInterfaceEmphasisFont } from '@core/layout/typographyReadiness.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import { createHeaderActionController } from '@core/headerActionBus.ts';
import { i18n } from '@core/i18n/index.ts';
import { runAbortable, signalAborted } from '@core/lifecycle/abortSignals.ts';
import { isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';
import { normalizeConversationId, readConversationIdFromRouteParameters, resolveMostRecentConversation, type ModelStreamReadiness } from '@features/chat/public.ts';
import { setupAutoSave, type ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { normalizeDetachedBootstrapParameters } from '@pages/chat/controllers/detached/chatDetachedBootstrap.ts';
import { configureDetachedEnvironment, type DetachedWindowHost } from '@pages/chat/controllers/detached/chatDetachedWindow.ts';
import { openDetachedChatWindow } from '@pages/chat/controllers/page/actions/detachedWindow.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatPreferencesHost } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatLifecycleResourcesHost } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ConversationInteractionFocusResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { applyInteractionFocus, interactionFocusUnavailableText } from '@pages/chat/controllers/page/interactionFocusController.ts';
import { applyChatAiSetupHandoff, type ChatAiSetupHandoffHost } from '@pages/chat/controllers/page/aisetuphandoff/effects.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';

interface ChatLiveUpdatesStatePort extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner, ChatPreferencesHost, ChatConversationViewHost, ChatConversationStateHost, ChatRuntimeServicesHost, ChatLifecycleResourcesHost {}

interface ChatLiveUpdatesUiPort extends ChatComposerHost, ChatModelSessionHost, ChatPagePresentationHost, ChatUiBehaviorsOwner, PageServicesOwnerHost, PageFeedbackOwnerHost {}

interface ChatLiveUpdatesHost extends ChatLiveUpdatesStatePort, ChatLiveUpdatesUiPort {
    aiSetupStorage: ChatAiSetupHandoffHost['storage'];
    conversationToolbarSession: ChatConversationToolbarManager;
    detachedWindowHost: DetachedWindowHost;
    initializeTokenCounterController(): void;
    syncResponsiveLayout(): void;
    resolveInteractionFocus(conversationId: string, focusNonce: string): Promise<ConversationInteractionFocusResponse>;
}

const activateMostRecentOrCreate = async (host: ChatLiveUpdatesHost): Promise<void> => {
    const mostRecentConversation = resolveMostRecentConversation(host.conversationState.conversations);
    if (mostRecentConversation !== null) {
        await host.conversationView.requireActions().activateConversationById(mostRecentConversation.id, { refreshUi: false, syncRoute: false });
    } else {
        await host.conversationView.requireActions().createConversation({ refreshUi: false, syncRoute: false });
    }
};

const resolveResumableConversationId = (host: ChatLiveUpdatesHost): string | null => {
    for (const candidate of [host.conversationState.currentConversationId, host.conversationRuntime.requireStorage().readLastConversationId()]) {
        const conversationId = normalizeConversationId(candidate);
        if (conversationId && host.conversationState.conversations.has(conversationId)) {
            return conversationId;
        }
    }
    return null;
};

const prepareChatPageInitialContent = async (host: ChatLiveUpdatesHost, parameters: JsonObject, signal: AbortSignal, chatLogger: (level: 'warn', message: string, error?: Error) => void): Promise<void> => {
    const shouldAbort = (): boolean => signalAborted(signal);
    const runStep = async (operation: () => Promise<void>): Promise<boolean> => runAbortable(signal, operation);
    fetchSystemLimits().catch((error) => {
        chatLogger('warn', 'Failed to fetch system limits', ensureError(error));
    });
    if (shouldAbort()) {
        return;
    }
    if (!(await runStep(() => host.conversationRuntime.requireStorage().loadState()))) {
        return;
    }
    if (!(await runStep(() => host.preferences.loadBackend()))) {
        return;
    }
    host.composerSurface.requireUi().showSyncSpinner();
    try {
        await host.conversationRuntime.requireStorage().loadConversationCatalogFromBackend();
    } finally {
        if (!shouldAbort()) {
            host.composerSurface.requireUi().hideSyncSpinner();
        }
    }
    if (shouldAbort()) {
        return;
    }
    host.conversationRuntime.requireStorage().subscribeToConversationEvents();
    host.initializeTokenCounterController();
    const bootstrapParameters: JsonObject = {};
    for (const [key, value] of Object.entries(parameters)) {
        if (isJsonValue(value)) {
            bootstrapParameters[key] = value;
        }
    }
    const detachedConversationId = host.services.isDetached() ? normalizeDetachedBootstrapParameters(bootstrapParameters).conversationId : null;
    const requestedConversationId = readConversationIdFromRouteParameters(Object.fromEntries(Object.entries(parameters).flatMap(([key, value]) => (typeof value === 'string' ? [[key, value]] : []))));
    const hasDetachedConversationId = detachedConversationId !== null && host.conversationState.conversations.has(detachedConversationId);
    const requestedOrDetachedConversationId = hasDetachedConversationId ? detachedConversationId : requestedConversationId;
    if (requestedOrDetachedConversationId) {
        if (host.conversationState.conversations.has(requestedOrDetachedConversationId)) {
            if (!(await runStep(() => host.conversationView.requireActions().activateConversationById(requestedOrDetachedConversationId, { refreshUi: false, syncRoute: false })))) {
                return;
            }
        } else {
            if (shouldAbort()) {
                return;
            }
            host.feedback.show(i18n.t('chat.errors.conversationUnavailable'), 'error');
            if (!(await runStep(() => activateMostRecentOrCreate(host)))) {
                return;
            }
        }
    } else {
        const resumableConversationId = resolveResumableConversationId(host);
        if (resumableConversationId) {
            if (!(await runStep(() => host.conversationView.requireActions().activateConversationById(resumableConversationId, { refreshUi: false, syncRoute: false })))) {
                return;
            }
        } else {
            if (!(await runStep(() => activateMostRecentOrCreate(host)))) {
                return;
            }
        }
    }
    if (shouldAbort()) {
        return;
    }
    host.conversationRuntime.requireStorage().saveChatState(true);
    host.composerSurface.requireUi().initialize();
    host.lifecycleResources.autoSaveCleanup?.();
    host.lifecycleResources.autoSaveCleanup = null;
    const autoSave = setupAutoSave(host.uiBehaviors);
    host.lifecycleResources.autoSaveCleanup = () => autoSave.dispose();
    host.presentation.insertIcons();
    host.conversationToolbarSession.initialize();
    configureDetachedEnvironment(host.detachedWindowHost, bootstrapParameters);
    if (!host.services.isDetached()) {
        const detachController = createHeaderActionController({ actionId: 'detach', contextId: 'chat' });
        detachController.show({ onClick: () => openDetachedChatWindow(host.detachedWindowHost) });
        host.lifecycleResources.detachAction = detachController;
    }
    if (shouldAbort()) {
        return;
    }
    if (
        !(await runStep(async () => {
            await host.uiBehaviors.layout.applySidebarState();
            const mainContainer = host.uiBehaviors.presentation.pageDom.require('.chat-main-container');
            await waitForElementAnimations(mainContainer, { signal });
        }))
    ) {
        return;
    }
    let streamReadiness: ModelStreamReadiness;
    try {
        streamReadiness = await raceWithAbortSignal(host.modelSession.ensureStream(), signal);
    } catch (error) {
        if (shouldAbort()) {
            return;
        }
        throw error;
    }
    if (streamReadiness.status !== 'ready') {
        const readinessReason = streamReadiness.reason ? streamReadiness.reason : streamReadiness.status;
        chatLogger('warn', `Chat model stream initialization did not become ready: ${readinessReason}`);
    }
    if (shouldAbort()) {
        return;
    }
    try {
        await prepareInterfaceEmphasisFont(host.uiBehaviors.presentation.pageDom.require('.chat-main-container').ownerDocument, signal);
    } catch (error) {
        if (shouldAbort()) return;
        chatLogger('warn', 'Chat emphasis font did not become ready', ensureError(error));
    }
    if (!(await runStep(() => host.conversationView.refresh()))) {
        return;
    }
    await applyInteractionFocus(
        {
            resolveInteractionFocus: (conversationId, focusNonce) => host.resolveInteractionFocus(conversationId, focusNonce),
            focusInteraction: (conversationId, interactionType, taskId) => host.composer.focusInteraction(conversationId, interactionType, taskId),
            showUnavailable: () => host.feedback.show(interactionFocusUnavailableText(), 'warning'),
            logWarning: (error) => chatLogger('warn', 'Failed to resolve Messaging interaction focus', error)
        },
        parameters,
        host.conversationState.currentConversationId,
        signal
    );
    if (shouldAbort()) {
        return;
    }
    host.syncResponsiveLayout();
    host.composerSurface.requireUi().applyExecutionControls();
    host.configurationRuntime.requireParameters().updateParameterUI();
    host.composer.applyInputActionVisibility();
    host.modelSession.updateUi();
    host.conversationView.initializeSearch();
    await runStep(async () => {
        await applyChatAiSetupHandoff(
            {
                storage: host.aiSetupStorage,
                isDetached: () => host.services.isDetached(),
                isCancelled: shouldAbort,
                currentConversation: () => host.conversationView.current(),
                createConversation: async () => {
                    await host.conversationView.requireActions().createConversation();
                },
                selectPrimaryModel: (modelId) => host.modelSession.selectPrimaryModel(modelId),
                isSelectableModel: (modelId) => {
                    const model = host.conversationState.modelIndex.get(modelId);
                    return model !== undefined && isChatSelectableModel(model);
                },
                updateConversationSettings: (conversationId, patch) => host.conversationRuntime.requireConversation().updateConversationSettings(conversationId, patch),
                refreshConversationSettings: (conversationId) => host.conversationView.requireActions().handleConversationSettingsAuthorityChangedEvent(conversationId)
            },
            parameters
        );
    });
};

export { prepareChatPageInitialContent };
export type { ChatLiveUpdatesHost };

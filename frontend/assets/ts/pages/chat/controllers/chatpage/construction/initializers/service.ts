/* SoAI - Chat page initializers service [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { ChatAttachmentManager, ChatAttachmentProcessor, ChatAudioManager, ChatConversationSettingsManager, ChatTtsManager, ChatUIManager, cloneSoaiPathDraftRecordContentPart, normalizeConversationId, type ConversationSettingsHost, type SoaiPathDraftRecord } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext, Logger } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import { requestConversationMessageWindow } from '@pages/chat/controllers/chatpage/construction/initializers/messageWindowPagingController.ts';
import { isThinkingFeatureEnabled } from '@pages/chat/controllers/page/state.ts';
import { applyWidescreenMode } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { resolveVoiceSttSettings } from '@pages/chat/controllers/voice/service.ts';

const initializeUIManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.composerSurface.hasUi()) {
        return;
    }
    const modelAvailability = page.state.conversationState.modelAvailability;
    if (!modelAvailability) {
        throw new Error('ChatPage requires model availability state');
    }
    const pendingMessageWindowRequests = new Set<string>();
    page.runtime.composerSurface.initializeUi(
        new ChatUIManager({
            sanitizer: page.platform.pageContext.sanitizer,
            optionalUI: (selector, context) => page.page.pageDom.optional(selector, context),
            queryUI: (selector, context) => page.page.pageDom.query(selector, context),
            toggleClassName: (element, className, add) => page.page.pageDom.toggleClass(element, className, add),
            updateAttribute: (element, attr, value) => page.page.pageDom.updateAttribute(element, attr, value),
            updateProperty: (element, prop, value) => page.page.pageDom.updateProperty(element, prop, value),
            updateHTML: (element, html, options?: { escape?: boolean }) => page.page.pageDom.updateHtml(element, html, options),
            getCachedIcon: (name, options) => page.sessions.presentation.cachedIcon(name, options),
            dom: {
                getDocument: () => page.platform.dom.getDocument(),
                getData: (element, key) => page.platform.dom.getData(element, key),
                setHTML: (element, html, options) => page.platform.dom.setHTML(element, html, options),
                setStyle: (element, prop, value) => page.platform.dom.setStyle(element, prop, value)
            },
            composition: {
                applyTextZoom: () => page.state.settings.applyTextZoom(),
                updateExportButtonVisibility: () => page.sessions.presentation.updateExportButtonVisibility(),
                applyWidescreenMode: () => applyWidescreenMode(page.sessions.uiBehaviors),
                applySidebarState: () => page.sessions.uiBehaviors.layout.applySidebarState()
            },
            sidebar: {
                getSidebarOpen: () => page.state.viewState.sidebarOpen,
                setSidebarOpen: (open) => {
                    page.state.viewState.sidebarOpen = open;
                },
                persistSidebarOpen: (open) => {
                    page.state.settings.storage.setChatSidebarOpen(open);
                }
            },
            session: {
                getCurrentConversationId: () => page.state.conversationState.currentConversationId,
                getCurrentConversation: () => page.sessions.conversationView.current(),
                getCurrentModel: () => page.state.conversationState.currentModel,
                getModelStreamHasPayload: () => modelAvailability.getModelStreamHasPayload(),
                isModelAvailable: (modelId) => modelAvailability.isModelAvailable(modelId),
                isConversationExecuting: (conversationId) => page.sessions.conversationView.isExecuting(conversationId),
                getTurnAdmission: (conversationId) => page.runtime.turnRuntime.requireStreaming().getCachedTurnAdmission(conversationId),
                hasActiveComparisonRun: (conversationId) => page.runtime.turnRuntime.requireStreaming().hasActiveComparisonRun(conversationId),
                isThinkingFeatureEnabled,
                hasPendingAttachmentProcessing: () => page.sessions.messageSending.hasPendingAttachmentProcessing()
            },
            messageManager: page.runtime.conversationRuntime.requireMessages(),
            hydrateToolImageProjection: (inputArguments) => page.platform.toolImages.hydrate(inputArguments),
            drafts: {
                getAttachments: () => {
                    const manager = page.runtime.composerSurface.optionalAttachments();
                    return manager ? manager.getAttachments() : null;
                },
                getRagIngestionStatus: () => page.sessions.messageSending.rag.currentStatus(),
                getDraftKnowledgeAttachments: () => page.sessions.messageSending.rag.currentKnowledgeDrafts(),
                refreshDraftKnowledgeAttachments: () => page.sessions.messageSending.rag.refreshKnowledgeDrafts(),
                cancelRagIngestion: () => page.sessions.messageSending.rag.cancelCurrent(),
                getConversationInputs: () => {
                    const conversationId = page.state.conversationState.currentConversationId;
                    if (!conversationId) {
                        return null;
                    }
                    const manager = page.runtime.turnRuntime.optionalConversationInputs();
                    if (!manager) {
                        return null;
                    }
                    const prompts = manager.getQueuedPrompts(conversationId);
                    return prompts.map((prompt) => ({
                        inputId: prompt.inputId,
                        inputType: prompt.inputType === 'steer' ? 'steer' : 'prompt',
                        state: prompt.state,
                        text: prompt.text,
                        attachmentContent: prompt.attachmentContent
                    }));
                },
                saveChatState: (force: boolean | undefined) => page.runtime.conversationRuntime.requireStorage().saveChatState(force),
                requestMessageWindow: (direction) => requestConversationMessageWindow(page, pendingMessageWindowRequests, direction)
            },
            runtime: {
                on: (target, event, handler, options) => page.page.pageResources.on(target, event, handler, options),
                createDebouncedHandler: (functionValue, delay) => page.page.services.createDebouncedHandler(functionValue, delay),
                setTimer: (functionValue, delay) => {
                    const timer = page.page.pageResources.setTimer(functionValue, delay);
                    if (timer === null) {
                        throw new Error('Chat page timer initialization failed');
                    }
                    return timer;
                },
                clearTimer: (timer) => page.page.pageResources.clearTimer(timer)
            }
        })
    );
};

const initializeConversationSettingsManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.configurationRuntime.hasConversationSettings()) {
        return;
    }
    const conversationSettingsHost: ConversationSettingsHost = {
        view: {
            on: (target, eventName, handler) => page.page.pageResources.on(target, eventName, handler),
            createElement: (tag, options, content) => page.page.pageElements.createElement(tag, options, content),
            appendToElement: (parent, child) => page.page.pageDom.append(parent, child),
            setUIValue: (element, value, options) => page.page.pageElements.setValue(element, value === null ? null : value === undefined ? undefined : String(value), options),
            updateHTML: (element, html, options?: { escape?: boolean }) => page.page.pageDom.updateHtml(element, html, options),
            updateText: (element, text) => page.page.pageDom.updateText(element, text),
            updateAttribute: (element, attr, value) => page.page.pageDom.updateAttribute(element, attr, value),
            updateProperty: (element, prop, value) => page.page.pageDom.updateProperty(element, prop, value),
            toggleClassName: (element, className, add) => page.page.pageDom.toggleClass(element, className, add),
            getIconSync: (name, options) => page.sessions.presentation.cachedIcon(name, options),
            dom: {
                getDocument: () => page.platform.dom.getDocument(),
                getData: (element, key) => page.platform.dom.getData(element, key),
                setStyle: (element, prop, value) => page.platform.dom.setStyle(element, prop, value)
            }
        },
        data: {
            storage: page.state.settings.storage,
            api: page.platform.api,
            conversationManager: {
                ensureConversationPersisted: (conversation) => page.runtime.conversationRuntime.requireConversation().ensureConversationPersisted(conversation),
                updateConversationSettings: (conversationId, patch) => page.runtime.conversationRuntime.requireConversation().updateConversationSettings(conversationId, patch)
            },
            storageManager: {
                saveState: (force?: boolean) => page.runtime.conversationRuntime.requireStorage().saveState(force)
            },
            getCurrentConversation: () => page.sessions.conversationView.current(),
            getCurrentModel: () => page.state.conversationState.currentModel,
            isConversationExecuting: (conversationId) => page.sessions.conversationView.isExecuting(conversationId)
        },
        rag: {
            getRagIngestionStatus: (conversationId) => page.sessions.messageSending.rag.statusForConversation(conversationId),
            subscribeRagIngestionStatus: (handler) => page.sessions.messageSending.rag.subscribeStatus(handler),
            startRagIngestion: async ({ conversationId, conversation, files, attachmentSource }) => {
                await page.sessions.messageSending.rag.start({ conversationId, conversation, files, attachmentSource });
            },
            cancelRagIngestion: (conversationId) => page.sessions.messageSending.rag.cancel(conversationId)
        },
        workflow: {
            isAdmin: () => getAuthManager().isAdmin(),
            applyMcpConfigToConversationModelSettings: (conversationId, config) => page.state.preferences.applyMcpConfig(conversationId, config),
            updateConversationWorkspacePathConfig: (conversationId, config) => page.state.preferences.updateWorkspacePath(conversationId, config),
            prepareMcpDefaultsProjection: () => page.state.preferences.prepareMcpDefaultsProjection(),
            prepareRagDefaultsProjection: () => page.state.preferences.prepareRagDefaultsProjection(),
            runWithBoundary: <T>(name: string, functionValue: () => Promise<T> | T) => page.page.pageLifecycle.run(name, functionValue),
            showNotification: (message, type, duration) => page.page.feedback.show(message, type, duration),
            setConversationSettingsSavePlan: (plan) => page.runtime.configurationRuntime.requireConfiguration().setConversationSettingsSavePlan(plan),
            activateConversationSettingsTab: (tabId) => page.sessions.configurationSession.openTab(tabId),
            ensureModelStream: () => page.sessions.modelSession.ensureStream(),
            get modelStreamHasPayload() {
                return page.state.conversationState.modelStreamHasPayload;
            },
            get models() {
                return page.state.conversationState.models;
            },
            invalidateChatMarkup: (scope) => page.sessions.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.sessions.conversationView.renderCurrent(),
            refreshTokenCounterPreview: () => page.sessions.composer.refreshTokenCounterPreview()
        }
    };
    page.runtime.configurationRuntime.initializeConversationSettings(
        new ChatConversationSettingsManager({
            host: conversationSettingsHost
        })
    );
};

const resolveConversationIdForAttachmentUpload = async (page: ChatControllerInitializationContext): Promise<string> => {
    let conversation = page.sessions.conversationView.current();
    if (!conversation) {
        conversation = await page.sessions.conversationView.requireActions().createConversation({ transferMode: 'adopt-current' });
    }
    if (!conversation) {
        throw new Error('Attachment upload requires an active conversation');
    }
    await page.runtime.conversationRuntime.requireConversation().ensureConversationPersisted(conversation);
    const conversationId = normalizeConversationId(conversation.id);
    if (!conversationId) {
        throw new Error('Attachment upload requires a valid conversation id');
    }
    return conversationId;
};

const loadSoaiPathImagePreview = async (page: ChatControllerInitializationContext, record: SoaiPathDraftRecord, signal: AbortSignal): Promise<string | null> => {
    const conversationId = page.state.conversationState.currentConversationId;
    if (!conversationId || !isPlainObject(record) || !isPlainObject(record.contentPart)) {
        return null;
    }
    const contentPart = cloneSoaiPathDraftRecordContentPart(record);
    const response = await page.platform.api.webui.chat.soaiPaths.download(conversationId, { contentPart: contentPart }, { rawResponse: true, signal });
    if (!(typeof Response === 'function' && response instanceof Response)) {
        throw new Error('SoAI path image preview download did not return a Response');
    }
    const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
    if (!response.ok || contentType.includes('application/json')) {
        return null;
    }
    if (signal.aborted || page.state.conversationState.currentConversationId !== conversationId) {
        return null;
    }
    const blob = await response.blob();
    if (signal.aborted || page.state.conversationState.currentConversationId !== conversationId) {
        return null;
    }
    return URL.createObjectURL(blob);
};

const initializeAttachmentManager = (page: ChatControllerInitializationContext, logger: Logger): void => {
    if (page.runtime.composerSurface.hasAttachments()) {
        return;
    }
    const deletePhysicalAttachment = page.platform.api.webui.chat.attachments.delete;
    const uiManager = page.runtime.composerSurface.requireUi();
    const attachmentProcessor = new ChatAttachmentProcessor({
        api: page.platform.api,
        resolveConversationId: () => resolveConversationIdForAttachmentUpload(page),
        runWithBoundary: <T>(scope: string, handler: () => Promise<T>) => page.page.pageLifecycle.run(scope, handler),
        uiManager
    });
    page.runtime.composerSurface.initializeAttachments(
        new ChatAttachmentManager({
            attachmentProcessor,
            uiManager,
            logger,
            errorHandler: (err, title, options) => page.page.feedback.handle(err, title, options),
            deletePhysicalAttachment: async (conversationId: string, attachmentId: string) => {
                return await deletePhysicalAttachment(conversationId, attachmentId, { signal: page.page.pageLifecycle.signal() ?? undefined });
            },
            loadSoaiPathImagePreview: (record, signal) => loadSoaiPathImagePreview(page, record, signal),
            subscribeAttachmentChanged: (listener) => subscribeManagedWebSocketContract({ label: 'ChatAttachments', contract: WEBSOCKET_EVENT_CONTRACTS.attachment.conversationChanged, handler: listener })
        })
    );
};

const initializeAudioManager = (page: ChatControllerInitializationContext): void => {
    if (page.sessions.voiceSession.hasAudio()) {
        return;
    }
    page.sessions.voiceSession.initializeAudio(
        new ChatAudioManager({
            apiClient: page.platform.api,
            resolveSttModel: () => resolveVoiceSttSettings(page.state.settings.parameters).model,
            beforeStart: async () => {
                await page.sessions.voiceSession.stopCallBeforeRecording();
            },
            onStateChange: (state) => page.sessions.elements.updateMicrophoneButtonState(state),
            onRecordingSnapshotChange: (snapshot) => page.runtime.composerSurface.requireUi().updateAudioRecordingPreview(snapshot),
            onError: (err, title, options) => page.page.feedback.handle(err, title, options),
            onTranscription: (text) => page.sessions.composer.insertTranscription(text)
        })
    );
};

const initializeTtsManager = (page: ChatControllerInitializationContext): void => {
    if (page.sessions.voiceSession.hasSpeech()) {
        return;
    }
    page.sessions.voiceSession.initializeSpeech(new ChatTtsManager({ apiClient: page.platform.api }));
};

export { initializeConversationSettingsManager, initializeUIManager, initializeAttachmentManager, initializeAudioManager, initializeTtsManager };

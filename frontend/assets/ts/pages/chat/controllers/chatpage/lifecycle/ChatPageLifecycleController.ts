/* SoAI - Chat page visibility, binding, initialization, and disposal ownership [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/ChatPageLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { parseChatStreamActivityResource } from '@core/chat/chatStreamActivitySnapshot.ts';
import { getStreamSubscriptions } from '@core/realtime/streammanager/streamManagerAccess.ts';
import { WEBUI_CHAT_ACTIVITY } from '@core/realtime/streammanager/resources/ids.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { bindChatAttachModalDragOpen } from '@pages/chat/controllers/chatpage/lifecycle/attachModalDragOpenBindingController.ts';
import { handleChatConversationRendered } from '@pages/chat/controllers/chatpage/lifecycle/conversationRenderedController.ts';
import type { ChatResponsiveLayoutSession } from '@pages/chat/controllers/chatpage/lifecycle/responsiveLayoutController.ts';
import { resumeChatPageVisibilityRuntime, suspendChatPageVisibilityRuntime } from '@pages/chat/controllers/chatpage/lifecycle/visibilityController.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { requireChatRoot } from '@pages/chat/dom.ts';
import type { AttachViewportResizeOptions } from '@core/routing/pages/pagetypes/public.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { isChatActionId } from '@pages/chat/actions.ts';
import { handleRootActionClick } from '@pages/chat/controllers/page/events/handlers.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';
import type { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatModelSessionManager } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import type { ChatComposerSurfaceRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatUiTaskScopeManager } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatLifecycleResources } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatConversationRenderOutcome } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface ChatLifecycleOperations {
    initializeTokenCounter(): void;
    prepareInitialContent(parameters: JsonObject, signal: AbortSignal, logger: ModuleLogger): Promise<void>;
    createRootEventsHost(signal: AbortSignal): ChatRootEventsHost;
    bindLocalizationEvents(signal: AbortSignal): void;
    handleInitialModal(): void;
    disposePage(): void;
    resumeStreamPresentation(): void;
    suspendStreamPresentation(): void;
    acquireStreamPresentation(): () => void;
}

interface ChatLifecycleControllerInitialization {
    ensureInitialized(): Promise<void>;
    dispatch(action: import('@features/chat/public.ts').ChatActionId, actionElement: HTMLElement, event: Event): void;
    requireActionHost(): import('@pages/chat/controllers/actionhandlers/core/contracts.ts').ChatActionHandlersHost;
    dispose(): void;
}

interface ChatLifecycleDependencies {
    composer: ChatComposerController;
    composerSurface: ChatComposerSurfaceRuntime;
    configurationSession: ChatConfigurationController;
    controllerInitialization: ChatLifecycleControllerInitialization;
    conversationRuntime: ChatConversationRuntime;
    conversationState: ChatConversationState;
    conversationToolbarSession: ChatConversationToolbarManager;
    conversationView: ChatConversationViewController;
    getDomContext(): Element | null;
    lifecycleResources: ChatLifecycleResources;
    modelSession: ChatModelSessionManager;
    operations: ChatLifecycleOperations;
    pageDom: PageDom;
    responsiveLayout: ChatResponsiveLayoutSession;
    runtimeServices: ChatRuntimeServices;
    services: PageServices;
    settings: ChatSettingsState;
    taskScope: ChatUiTaskScopeManager;
    turnRuntime: ChatTurnRuntime;
    voiceSession: ChatVoiceSessionHost['voiceSession'];
}

interface LifecycleControls {
    abortListeners(reason: string): void;
    resetListenersAbortSignal(): AbortSignal;
    attachViewportResize(handler: () => void, options: AttachViewportResizeOptions): () => void;
}

class ChatPageLifecycleController {
    readonly #page: ChatLifecycleDependencies;
    readonly #controls: LifecycleControls;
    readonly #logger: ModuleLogger;
    #rootEventsHost: ChatRootEventsHost | null = null;
    readonly #conversationRenderedExit: () => void;

    constructor(page: ChatLifecycleDependencies, controls: LifecycleControls, logger: ModuleLogger) {
        this.#page = page;
        this.#controls = controls;
        this.#logger = logger;
        this.#conversationRenderedExit = page.conversationView.onRendered((outcome) => this.#afterConversationRendered(outcome));
    }

    syncResponsiveLayout(): void {
        this.#page.responsiveLayout.sync();
    }

    afterConversationRendered(): void {
        this.#afterConversationRendered('dom-reconciled');
    }

    #afterConversationRendered(outcome: ChatConversationRenderOutcome = 'dom-reconciled'): void {
        if (this.#page.lifecycleResources.isDestroyed) return;
        handleChatConversationRendered({
            host: this.#page,
            handleTokenCounterConversationRendered: (conversationId) => this.#page.composer.handleConversationRendered(conversationId),
            outcome
        });
        this.#page.runtimeServices.presence.setConversationId(this.#page.conversationState.currentConversationId);
        this.#page.conversationView.acknowledgeTerminalAttentionIfViewed(this.#page.conversationState.currentConversationId);
    }

    async afterInitialize(result: boolean): Promise<boolean> {
        if (result) {
            this.#page.lifecycleResources.presenceExit?.();
            this.#page.lifecycleResources.presenceExit = this.#page.runtimeServices.presence.enter();
            this.#page.lifecycleResources.activePresenceExit?.();
            this.#page.lifecycleResources.activePresenceExit = this.#page.runtimeServices.presence.setActiveConversationChangeHandler((conversationId): void => {
                if (conversationId !== null && !this.#page.lifecycleResources.isDestroyed) this.#afterConversationRendered();
            });
            this.#page.lifecycleResources.presentationPresenceExit?.();
            this.#page.lifecycleResources.presentationPresenceExit = this.#page.runtimeServices.presence.setPresentationStateChangeHandler((state): void => {
                if (!this.#page.lifecycleResources.isDestroyed) this.#page.runtimeServices.chatStream.setPresentationState(state);
            });
            this.#page.runtimeServices.presence.setPageVisible(true);
        }
        await this.#page.settings.storage.ready;
        if (!this.#page.settings.textZoomInitialized) {
            this.#page.settings.textZoom = this.#page.settings.textZoomController.initialize(this.#page.settings.textZoomPageHost);
            this.#page.settings.textZoomInitialized = true;
        }
        return result;
    }

    async hide(): Promise<void> {
        this.#page.operations.suspendStreamPresentation();
        this.#page.lifecycleResources.suspendStreamPresentation();
        this.#page.lifecycleResources.chatActivityExit?.();
        this.#page.lifecycleResources.chatActivityExit = null;
        this.#page.runtimeServices.presence.setPageVisible(false);
        await suspendChatPageVisibilityRuntime({
            saveStorageState: () => this.#page.conversationRuntime.requireStorage().saveState(true),
            stopVoiceCallIfHidden: async () => this.#page.voiceSession.stopCall('hide'),
            disposeAudioManager: () => this.#page.voiceSession.disposeAudio(),
            stopTtsManager: () => this.#page.voiceSession.stopSpeaking(),
            clearViewportResizeCleanup: () => this.#page.lifecycleResources.clearViewportResizeCleanup()
        });
    }

    cancel(): void {
        this.#page.operations.suspendStreamPresentation();
        this.#page.lifecycleResources.cancelPageUi(this.#page.taskScope);
    }

    async prepareInitialContent(parameters: JsonObject | undefined, context: { signal?: AbortSignal }): Promise<void> {
        const controller = this.#page.lifecycleResources.getAfterInitializeAbortController();
        if (!controller) throw new Error('ChatPageLifecycleController requires an after-init abort controller');
        const signal = context.signal ?? controller.signal;
        try {
            await this.#page.operations.prepareInitialContent(parameters ?? {}, signal, this.#logger);
        } catch (error) {
            if (signal.aborted) return;
            throw error;
        }
    }

    async startLiveUpdates(context: { signal?: AbortSignal; setStage?(stage: string): void }): Promise<void> {
        const signal = context.signal ?? this.#page.lifecycleResources.getAfterInitializeAbortController()?.signal;
        if (!signal) throw new Error('ChatPageLifecycleController requires a live update abort signal');
        if (signal.aborted) return;
        context.setStage?.('chatFirstRun');
        await this.#page.runtimeServices.firstRunModals.handlePageShow('chat');
        if (signal.aborted || this.#page.lifecycleResources.isDestroyed) return;
        this.#page.lifecycleResources.streamPresentationExit?.();
        const streamPresentationExit = this.#page.operations.acquireStreamPresentation();
        this.#page.lifecycleResources.streamPresentationExit = streamPresentationExit;
        try {
            this.#page.operations.resumeStreamPresentation();
        } catch (error) {
            streamPresentationExit();
            this.#page.lifecycleResources.streamPresentationExit = null;
            throw error;
        }
        context.setStage?.('chatVisibility');
        this.#page.runtimeServices.presence.setPageVisible(true);
        if (!this.#page.lifecycleResources.isDestroyed && this.#page.runtimeServices.presence.isActivelyViewingConversation(this.#page.conversationState.currentConversationId)) this.#afterConversationRendered();
        if (signal.aborted) return;
        this.#page.lifecycleResources.chatActivityExit?.();
        this.#page.lifecycleResources.chatActivityExit = getStreamSubscriptions().subscribeResourceValue(WEBUI_CHAT_ACTIVITY, (value): void => {
            if (this.#page.lifecycleResources.isDestroyed) {
                return;
            }
            const activity = parseChatStreamActivityResource(value);
            const previousActiveIds = this.#page.conversationState.activeChatConversationIds;
            const nextActiveIds = new Set(activity.activeConversationIds);
            let changed = previousActiveIds.size !== nextActiveIds.size;
            if (!changed) {
                for (const conversationId of previousActiveIds) {
                    if (!nextActiveIds.has(conversationId)) {
                        changed = true;
                        break;
                    }
                }
            }
            if (!changed) {
                return;
            }
            const currentConversationId = this.#page.conversationState.currentConversationId;
            const currentConversationActivityChanged = currentConversationId !== null && previousActiveIds.has(currentConversationId) !== nextActiveIds.has(currentConversationId);
            this.#page.conversationState.activeChatConversationIds = nextActiveIds;
            terminateHandledPromise(currentConversationActivityChanged ? this.#page.conversationView.refresh() : this.#page.conversationView.renderList());
        });
        await resumeChatPageVisibilityRuntime({
            signal,
            clearViewportResizeCleanup: () => this.#page.lifecycleResources.clearViewportResizeCleanup(),
            syncResponsiveLayout: () => this.syncResponsiveLayout(),
            attachViewportResize: (handler, options) => this.#controls.attachViewportResize(handler, options),
            setViewportResizeCleanup: (cleanup) => this.#page.lifecycleResources.setViewportResizeCleanup(cleanup),
            conversationState: this.#page.conversationState,
            conversationView: this.#page.conversationView
        });
    }

    async destroy(): Promise<void> {
        this.#page.operations.suspendStreamPresentation();
        this.#controls.abortListeners('chat-page-destroy');
        this.#page.lifecycleResources.beginDestroy(this.#page.taskScope);
        this.#page.turnRuntime.requireAgent().dispose();
        await this.#page.voiceSession.dispose();
        this.#page.lifecycleResources.clearViewportResizeCleanup();
        this.#page.operations.disposePage();
        this.#conversationRenderedExit();
        this.#page.controllerInitialization.dispose();
        this.#rootEventsHost = null;
    }

    async beforeInitialize(): Promise<void> {
        this.#page.lifecycleResources.resetAfterInitializeAbortController();
        await this.#page.controllerInitialization.ensureInitialized();
    }

    bindPageEvents(): void {
        const rootElement = requireChatRoot({ getDomContext: () => this.#page.getDomContext() });
        const signal = this.#controls.resetListenersAbortSignal();
        this.#rootEventsHost = this.#page.operations.createRootEventsHost(signal);
        const rootEventsHost = this.#rootEventsHost;
        bindDataActionListener({
            root: rootElement,
            eventType: 'click',
            signal,
            isAction: isChatActionId,
            preventDefault: 'never',
            onAction: ({ event, action, actionElement }): void => handleRootActionClick(rootEventsHost, event, action, actionElement)
        });
        bindChatAttachModalDragOpen(
            {
                conversationState: this.#page.conversationState,
                conversationToolbarSession: this.#page.conversationToolbarSession,
                getDomContext: () => this.#page.getDomContext(),
                requireActionHost: () => this.#page.controllerInitialization.requireActionHost()
            },
            signal
        );
        this.#page.operations.bindLocalizationEvents(signal);
        this.#page.configurationSession.bindEvents(rootElement, signal, () => this.#rootEventsHost);
        this.#page.conversationView.initializeEmptyStateNavigation(rootElement);
        if (!this.#page.services.isDetached()) this.#page.operations.handleInitialModal();
    }
}

export { ChatPageLifecycleController };
export type { ChatLifecycleControllerInitialization, ChatLifecycleDependencies, ChatLifecycleOperations, LifecycleControls };

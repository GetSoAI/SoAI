/* SoAI - Chat routed page [frontend/assets/ts/pages/chat/ChatPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { buildChatPageMarkup } from '@pages/chat/view.ts';
import { PAGE_ID, PAGE_MODULE_ID } from '@pages/chat/contracts/chatPageSupport.ts';
import { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import { ChatPromptPickerController } from '@pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts';
import { ChatCharacterMapController } from '@pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts';
import { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import { ChatPageElementsManager } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import { ChatModelSessionManager } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import type { DetachedWindowHost } from '@pages/chat/controllers/detached/chatDetachedWindow.ts';
import { CHAT_COMPOSER_ACTIONS_COLLAPSE_BREAKPOINT_PX } from '@pages/chat/contracts/constants.ts';
import { ChatPageLifecycleController } from '@pages/chat/controllers/chatpage/lifecycle/ChatPageLifecycleController.ts';
import { ChatConversationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import { ChatTurnRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import { ChatComposerSurfaceRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import { ChatConfigurationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import { ChatLifecycleResources } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatRuntimeServices, ChatPageDependencies } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import { ChatViewState } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatUiTaskScopeManager } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { composeChatPageRuntime } from '@pages/chat/controllers/chatpage/runtime/composeChatPageRuntime.ts';
import { syncChatHeaderActionLayout, type UiBehaviorHost } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatMessageSendingController } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatVoiceSession } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

const log = createModuleLogger('ChatPage', { defaultLevel: 'info' });

class ChatPage extends StaticBasePage {
    readonly conversationState = new ChatConversationState();
    readonly conversationRuntime = new ChatConversationRuntime();
    readonly turnRuntime = new ChatTurnRuntime();
    readonly composerSurface = new ChatComposerSurfaceRuntime();
    readonly configurationRuntime = new ChatConfigurationRuntime();
    readonly settings: ChatSettingsState;
    readonly viewState = new ChatViewState();
    readonly lifecycleResources = new ChatLifecycleResources();
    readonly runtimeServices: ChatRuntimeServices;
    readonly uiBehaviors: UiBehaviorHost;
    readonly taskScope: ChatUiTaskScopeManager;
    readonly elements: ChatPageElementsManager;
    readonly configurationSession: ChatConfigurationController;
    readonly conversationToolbarSession: ChatConversationToolbarManager;
    readonly promptPickerSession: ChatPromptPickerController;
    readonly characterMapSession: ChatCharacterMapController;
    readonly preferences: ChatPreferencesManager;
    readonly conversationView: ChatConversationViewController;
    readonly composer: ChatComposerController;
    readonly modelSession: ChatModelSessionManager;
    readonly presentation: ChatPagePresentationController;
    readonly controllerInitialization: { ensureInitialized(): Promise<void> };
    readonly detachedWindowHost: DetachedWindowHost;
    readonly messageSending: ChatMessageSendingController;
    readonly lifecycle: ChatPageLifecycleController;
    readonly voiceSession: ChatVoiceSession;
    constructor(dependencies: ChatPageDependencies, basePageDependencies: BasePageDependencies) {
        super('chat', { dependencies: basePageDependencies });
        this.layout.configure({
            getActionsMenuBreakpoint: () => CHAT_COMPOSER_ACTIONS_COLLAPSE_BREAKPOINT_PX,
            getActionsMenuSidebarState: () => this.viewState.sidebarOpen,
            onActionsMenuCollapsedChange: () => syncChatHeaderActionLayout(this.uiBehaviors)
        });
        const composition = composeChatPageRuntime(
            {
                domain: {
                    conversationRuntime: this.conversationRuntime,
                    turnRuntime: this.turnRuntime,
                    composerSurface: this.composerSurface,
                    configurationRuntime: this.configurationRuntime,
                    conversationState: this.conversationState,
                    viewState: this.viewState,
                    lifecycleResources: this.lifecycleResources
                },
                page: {
                    pageDom: this.pageDom,
                    pageElements: this.pageElements,
                    pageResources: this.pageResources,
                    pageLifecycle: this.pageLifecycle,
                    layout: this.layout,
                    streaming: this.streaming,
                    services: this.services,
                    feedback: this.feedback,
                    pageHost: this.pageHost
                },
                platform: {
                    pageContext: this.pageContext,
                    stateManager: this.dependencies.stateManager,
                    api: this.dependencies.api,
                    router: this.dependencies.router,
                    dom: this.dependencies.dom,
                    storage: this.dependencies.storage
                }
            },
            dependencies,
            log
        );
        this.runtimeServices = composition.runtimeServices;
        this.uiBehaviors = composition.uiBehaviors;
        this.settings = composition.settings;
        this.taskScope = composition.taskScope;
        this.elements = composition.elements;
        this.preferences = composition.preferences;
        this.conversationView = composition.conversationView;
        this.presentation = composition.presentation;
        this.modelSession = composition.modelSession;
        this.composer = composition.composer;
        this.configurationSession = composition.configuration;
        this.conversationToolbarSession = composition.toolbar;
        this.promptPickerSession = composition.promptPicker;
        this.characterMapSession = composition.characterMap;
        this.voiceSession = composition.voiceSession;
        this.controllerInitialization = composition.controllerInitialization;
        this.detachedWindowHost = composition.detachedWindowHost;
        this.messageSending = composition.messageSending;
        this.lifecycle = composition.lifecycle;
    }

    syncResponsiveLayout(): void {
        this.lifecycle.syncResponsiveLayout();
    }
    protected override async afterInitialization(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterInitialization(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.lifecycle.afterInitialize(true);
    }
    override async onHide(): Promise<void> {
        await this.lifecycle.hide();
        await super.onHide();
    }
    protected override onCancel(_reason: string): void {
        this.lifecycle.cancel();
    }
    override async prepareInitialContent(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.prepareInitialContent(parameters, context);
        await this.lifecycle.prepareInitialContent(parameters, context);
    }
    override async startLiveUpdates(parameters?: JsonObject, context: { signal?: AbortSignal; setStage?(stage: string): void } = {}): Promise<void> {
        await super.startLiveUpdates(parameters, context);
        context.setStage?.('chatVisibility');
        await this.lifecycle.startLiveUpdates(context);
    }

    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.composerSurface.requireUi().updateInputState();
    }

    override async onDestroy(): Promise<void> {
        await this.lifecycle.destroy();
    }
    override async renderView(): Promise<TrustedHtml> {
        return toTrustedHtml(buildChatPageMarkup(this.pageContext.sanitizer, this.services.isDetached()));
    }
    override async beforePageInitialize(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.lifecycle.beforeInitialize();
    }
    bindPageEvents(): void {
        this.lifecycle.bindPageEvents();
    }
    override getRequiredResources(): string[] {
        return [MODELS];
    }
    override async onRefresh(parameters: JsonObject | null): Promise<void> {
        await super.onRefresh(parameters);
        this.conversationView.invalidate('both');
        this.viewState.iconCache.clear();
        const streamReadiness = await this.modelSession.ensureStream();
        if (streamReadiness.status !== 'ready') {
            const readinessReason = streamReadiness.reason ? streamReadiness.reason : streamReadiness.status;
            throw new Error(`Chat model stream refresh failed: ${readinessReason}`);
        }
        this.modelSession.updateUi();
        await this.conversationView.refresh();
    }
}

export { ChatPage, PAGE_ID, PAGE_MODULE_ID };
export type { ChatPageDependencies };

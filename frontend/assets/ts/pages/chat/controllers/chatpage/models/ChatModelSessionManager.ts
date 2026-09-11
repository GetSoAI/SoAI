/* SoAI - Chat model selection, readiness, and model-dependent UI ownership [frontend/assets/ts/pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasDataActionElement } from '@core/dom/dataAction.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { CHAT_SELECTORS, resolveMessageSenderLabel, type ConversationMessage, type ConversationProjectionAnalysis, type ModelStreamReadiness } from '@features/chat/public.ts';
import { notifyModelSelectionChangedIfNeeded, syncAssistantHeaderCatalogStateForPage } from '@pages/chat/controllers/chatpage/construction/modeluisync/service.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { applyModelContextWindowConstraints } from '@pages/chat/controllers/page/dom/modelContextWindowConstraintsController.ts';
import { syncCameraInputActionSupport } from '@pages/chat/controllers/page/dom/cameraController.ts';
import { updateVoiceAudioModelOptions } from '@pages/chat/controllers/page/dom/voice.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { ChatModelSessionContract, ComparisonPresentationState } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatComparisonTurnNavigationController } from '@pages/chat/widgets/comparisonturn/ChatComparisonTurnNavigationController.ts';
import type { ChatModelsController } from '@pages/chat/controllers/chatmodelscontroller/ChatModelsController.ts';
import type { ChatModelControlController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts';

interface ChatModelSessionDependencies {
    runtime: {
        composerSurface: ChatComposerSurfaceRuntimeOwner['composerSurface'];
        configurationRuntime: ChatConfigurationRuntimeOwner['configurationRuntime'];
        conversationRuntime: ChatConversationRuntimeOwner['conversationRuntime'];
        turnRuntime: ChatTurnRuntimeOwner['turnRuntime'];
    };
    state: {
        conversationState: ChatConversationStateHost['conversationState'];
        settings: ChatSettingsStateHost['settings'];
    };
    page: {
        pageDom: ChatPageDomHost['pageDom'];
        streaming: PageStreamingOwnerHost['streaming'];
        taskScope: ChatUiTaskScopeHost['taskScope'];
    };
    platform: {
        stateManager: Parameters<typeof syncAssistantHeaderCatalogStateForPage>[0]['stateManager'];
        dom: ChatPageDomHost['dom'] & { getDocument(): Document };
        getDomContext(): Element | null;
    };
    comparisonNavigation: ChatComparisonTurnNavigationController;
}

class ChatModelSessionManager implements ChatModelSessionContract {
    readonly #page: ChatModelSessionDependencies;
    #lastNotifiedSelection: string | null = null;
    #models: ChatModelsController | null = null;
    #modelControl: ChatModelControlController | null = null;

    constructor(page: ChatModelSessionDependencies) {
        this.#page = page;
    }

    dispose(): void {
        this.#page.comparisonNavigation.dispose();
        this.#models = null;
        this.#modelControl = null;
    }

    initializeModelControllers(models: ChatModelsController, modelControl: ChatModelControlController): void {
        if (this.#models || this.#modelControl) {
            throw new Error('Chat model controllers are already initialized');
        }
        this.#models = models;
        this.#modelControl = modelControl;
    }

    async ensureStream(): Promise<ModelStreamReadiness> {
        const runtime = await this.#page.page.streaming.ensureRuntime();
        await runtime.resources.ensureResourceStarted(MODELS);
        return this.#requireModels().ensureModelStream();
    }

    resolveKey(candidate: string | null | undefined): string | null {
        return this.#requireModels().resolveModelKey(candidate);
    }

    displayName(modelId: string | null): string {
        return this.#requireModels().getModelDisplayName(modelId);
    }

    messageSenderLabel(message: ConversationMessage, role: string): string {
        return resolveMessageSenderLabel({
            message,
            role,
            parameters: this.#page.state.settings.parameters,
            conversation: this.#page.state.conversationState.currentConversationId === null ? null : (this.#page.state.conversationState.conversations.get(this.#page.state.conversationState.currentConversationId) ?? null),
            currentModel: this.#page.state.conversationState.currentModel,
            getModelDisplayName: (modelId) => this.displayName(modelId)
        });
    }

    updateUi(root?: Element): void {
        this.#modelControl?.render();
        applyModelContextWindowConstraints({ conversationRuntime: this.#page.runtime.conversationRuntime, conversationState: this.#page.state.conversationState, settings: this.#page.state.settings, pageDom: this.#page.page.pageDom });
        syncCameraInputActionSupport({ pageDom: this.#page.page.pageDom });
        this.#page.runtime.composerSurface.requireUi().updateInputState();
        updateVoiceAudioModelOptions({ pageDom: this.#page.page.pageDom }, this.#page.state.conversationState.models, this.#page.runtime.configurationRuntime.requireConfiguration().getWorkingParameters(), root);
        this.syncHeaderCatalog(root);
        notifyModelSelectionChangedIfNeeded({
            currentModel: this.#page.state.conversationState.currentModel,
            getLastNotifiedModelSelection: () => this.#lastNotifiedSelection,
            setLastNotifiedModelSelection: (modelId) => {
                this.#lastNotifiedSelection = modelId;
            },
            dispatchEvent: (event) => this.#page.platform.dom.getDocument().dispatchEvent(event)
        });
    }

    syncHeaderCatalog(root?: Element): void {
        syncAssistantHeaderCatalogStateForPage({ conversationState: this.#page.state.conversationState, stateManager: this.#page.platform.stateManager, getDomContext: this.#page.platform.getDomContext }, root);
    }

    closeControlMenu(): void {
        this.#modelControl?.closeMenu();
    }

    handleControlAction(actionElement: HTMLElement): void {
        const controller = this.#modelControl;
        if (!controller) return;
        const action = hasDataActionElement(actionElement) ? actionElement.dataset.action : 'missing-action';
        this.#page.page.taskScope.run(`chat:modelControl:${action}`, async () => controller.handleAction(actionElement));
    }

    handleControlSearchInput(input: HTMLInputElement): void {
        this.#modelControl?.handleSearchInput(input);
    }

    handleComparisonNavigation(actionElement: HTMLElement): void {
        const controller = this.#page.comparisonNavigation;
        const assistantTurnTimestamp = controller.resolveAssistantTurnTimestampFromActionElement(actionElement);
        const direction = controller.resolveDirectionFromActionElement(actionElement);
        const variantCount = controller.resolveVariantCountFromActionElement(actionElement);
        if (assistantTurnTimestamp === null || direction === null || variantCount === null) {
            throw new Error('Chat comparison navigation requires assistantTurnTimestamp and comparison variant count');
        }
        controller.navigate({ assistantTurnTimestamp, direction, variantCount });
        const messages = this.#page.page.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
        if (!(messages instanceof HTMLElement)) return;
        const conversationId = this.#page.state.conversationState.currentConversationId;
        controller.syncCarousels(messages, {
            isCurrentStreaming: Boolean(conversationId && this.#page.runtime.turnRuntime.requireStreaming().isStreamingConversation(conversationId)),
            activeComparisonRun: conversationId ? this.#page.runtime.turnRuntime.requireStreaming().getActiveComparisonRun(conversationId) : null
        });
        controller.sync(messages);
    }

    syncComparisonSelection(analysis: ConversationProjectionAnalysis): ReadonlyMap<number, number> {
        this.#page.comparisonNavigation.syncSelectionFromAnalysis(analysis);
        return this.#page.comparisonNavigation.resolveActiveVariantIndexByAssistantTurnTimestamp();
    }

    syncComparisonPresentation(container: Element, state: ComparisonPresentationState): void {
        this.#page.comparisonNavigation.syncCarousels(container, state);
        this.#page.comparisonNavigation.sync(container);
    }

    #requireModels(): ChatModelsController {
        if (!this.#models) throw new Error('Chat models controller is not initialized');
        return this.#models;
    }
}

export { ChatModelSessionManager };
export type { ChatModelSessionContract, ChatModelSessionDependencies };
export type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';

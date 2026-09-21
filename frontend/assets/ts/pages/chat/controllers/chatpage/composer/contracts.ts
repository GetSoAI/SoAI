/* SoAI - Chat composer ownership contracts [frontend/assets/ts/pages/chat/controllers/chatpage/composer/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { SecretPromptInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { ChatComposerDraftManager, ChatElicitationSession, ComposerDraftFlushOptions } from '@features/chat/public.ts';
import type { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationViewContract } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatUiTaskScopeContract } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatTokenCounterController } from '@pages/chat/widgets/tokencounter/ChatTokenCounterController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import type { ChatComposerInputController } from '@pages/chat/controllers/chatpage/composer/ChatComposerInputController.ts';

interface ChatComposerDependencies {
    runtime: {
        composerSurface: ChatComposerSurfaceRuntimeOwner['composerSurface'];
        configurationRuntime: ChatConfigurationRuntimeOwner['configurationRuntime'];
        conversationRuntime: ChatConversationRuntimeOwner['conversationRuntime'];
        turnRuntime: ChatTurnRuntimeOwner['turnRuntime'];
    };
    page: {
        pageDom: PageDomOwnerHost['pageDom'];
        feedback: PageFeedbackOwnerHost['feedback'];
        services: PageServicesOwnerHost['services'];
        pageElements: PageUiOwnerHost['pageElements'];
        getLifecycleSignal(): AbortSignal | null;
    };
    state: {
        settings: ChatSettingsState;
        conversationState: ChatConversationState;
    };
    sessions: {
        taskScope: ChatUiTaskScopeContract;
        preferences: ChatPreferencesManager;
        conversationView: ChatConversationViewContract;
        presentation: ChatPagePresentationController;
        voiceSession: ChatVoiceSessionHost['voiceSession'];
    };
    platform: {
        api: ApiClient;
        dom: ChatPageDomHost['dom'];
    };
    input: ChatComposerInputController;
}

interface ChatComposerContract {
    handleAgentKeyDown(event: KeyboardEvent): boolean;
    toggleCall(): void;
    cycleTokenCounter(): void;
    cancelConversationInput(conversationId: string, inputId: string): Promise<void>;
    retryConversationRegeneration(conversationId: string, inputId: string): Promise<void>;
    resolveAskUserPrompt(conversationId: string, taskId: string, action: 'submit' | 'cancel'): Promise<void>;
    resolveSecretPrompt(conversationId: string, taskId: string, request: SecretPromptInteractionResolutionRequest): Promise<void>;
    resolveToolApprovalPrompt(conversationId: string, taskId: string, action: 'approve' | 'deny'): Promise<void>;
    handleInputHistoryNavigation(input: HTMLTextAreaElement, direction: 'up' | 'down'): boolean;
    noteDraftChanged(value: string): void;
    refreshTokenCounterPreview(): void;
    handleConversationRendered(conversationId: string | null): void;
    applyParameterValueFromElement(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): void;
    insertTranscription(text: string): void;
    insertTextAtCaret(text: string, mode: 'inline' | 'block'): void;
    resizeInput(textarea: Element): void;
    updateEmptyStateInputHint(): void;
    updateInputState(): void;
    applyInputActionVisibility(): void;
    toggleTools(): Promise<void>;
    syncToolsEnabled(enabled: boolean): Promise<void>;
    syncToolApprovalRequired(required: boolean): Promise<void>;
    persistParameters(): void;
    clearInput(): void;
    initializeTokenCounter(controller: ChatTokenCounterController): void;
    hasTokenCounter(): boolean;
    disposeTokenCounter(): void;
    handleConversationChanged(conversationId: string | null): void;
    handleModelChanged(modelId: string | null): void;
    handleConversationPersisted(conversationId: string): void;
    noteConversationContentCommitted(): void;
    syncTokenCounterEnabledState(): void;
    initializeElicitation(session: ChatElicitationSession): void;
    hasElicitation(): boolean;
    disposeElicitation(): void;
    focusInteraction(conversationId: string, interactionType: 'ask_user' | 'tool_approval' | 'vault_secret_request', taskId: string): void;
    initializeDraft(manager: ChatComposerDraftManager): void;
    draftManager(): ChatComposerDraftManager | null;
    flushDraft(reason: string, options?: ComposerDraftFlushOptions): Promise<void>;
    disposeDraft(): void;
}

interface ChatComposerHost {
    composer: ChatComposerContract;
}

export type { ChatComposerContract, ChatComposerDependencies, ChatComposerHost };

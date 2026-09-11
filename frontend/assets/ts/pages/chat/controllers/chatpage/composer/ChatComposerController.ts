/* SoAI - Chat composer interaction and prompt resolution ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatComposerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecretPromptInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { handleToggleToolsForPage } from '@pages/chat/controllers/chatpage/construction/callbackHandlers.ts';
import { resolveAskUserPromptForConstruction } from '@pages/chat/controllers/chatpage/construction/askUserPromptResolution.ts';
import { resolveSecretPromptForConstruction } from '@pages/chat/controllers/chatpage/construction/secretPromptResolutionController.ts';
import { resolveToolApprovalPromptForConstruction } from '@pages/chat/controllers/chatpage/construction/toolapproval/service.ts';
import { handleVoiceCallToggleForPage } from '@pages/chat/controllers/chatpage/construction/voicecall/actions.ts';
import type { ChatTokenCounterController } from '@pages/chat/widgets/tokencounter/ChatTokenCounterController.ts';
import { insertTranscription, refreshChatInputUiState } from '@pages/chat/controllers/page/dom/input.ts';
import { persistParametersToConversation } from '@pages/chat/controllers/chatpage/construction/persistConversationParameters.ts';
import { syncToolApprovalRequiredToConversation, syncToolsEnabledToConversation, type SyncToolsEnabledHost } from '@pages/chat/controllers/chatpage/construction/syncToolsEnabled.ts';
import type { ChatComposerDraftManager, ChatElicitationSession, ComposerDraftFlushOptions } from '@features/chat/public.ts';
import type { ChatComposerContract, ChatComposerDependencies } from '@pages/chat/controllers/chatpage/composer/contracts.ts';
import { applyInputActionVisibilityLifecycle } from '@pages/chat/controllers/chatpage/construction/inputActionVisibilityController.ts';
import { ChatComposerSession } from '@pages/chat/controllers/chatpage/composer/ChatComposerSession.ts';
import { ChatPromptHistoryNavigationController } from '@pages/chat/controllers/ChatPromptHistoryNavigationController.ts';

class ChatComposerController implements ChatComposerContract {
    readonly #dependencies: ChatComposerDependencies;
    readonly #session: ChatComposerSession;
    readonly #promptHistory: ChatPromptHistoryNavigationController;

    constructor(dependencies: ChatComposerDependencies) {
        this.#dependencies = dependencies;
        this.#session = new ChatComposerSession(dependencies.page.pageDom);
        this.#promptHistory = new ChatPromptHistoryNavigationController({
            api: dependencies.platform.api.webui.chat.promptHistory,
            taskScope: dependencies.sessions.taskScope,
            getInput: () => dependencies.input.getChatInput(),
            getLifecycleSignal: () => dependencies.page.getLifecycleSignal(),
            applyValue: (input, value) => this.#applyPromptHistoryValue(input, value),
            reportFailure: (error, title) => dependencies.page.feedback.handle(error, title, { notify: true })
        });
    }

    handleAgentKeyDown(event: KeyboardEvent): boolean {
        return this.#dependencies.runtime.turnRuntime.requireAgent().handleKeyDown(event);
    }

    toggleCall(): void {
        handleVoiceCallToggleForPage({ voiceSession: this.#dependencies.sessions.voiceSession, runUiTask: (operationId, task) => this.#dependencies.input.runUiTask(operationId, task) });
    }

    cycleTokenCounter(): void {
        this.#session.cycleTokenCounter();
    }

    initializeTokenCounter(controller: ChatTokenCounterController): void {
        this.#session.initializeTokenCounter(controller);
    }

    hasTokenCounter(): boolean {
        return this.#session.hasTokenCounter;
    }

    disposeTokenCounter(): void {
        this.#session.disposeTokenCounter();
    }

    handleConversationChanged(conversationId: string | null): void {
        this.#promptHistory.invalidate();
        this.#session.withTokenCounter((controller) => controller.handleConversationChanged(conversationId));
    }

    handleModelChanged(modelId: string | null): void {
        this.#session.withTokenCounter((controller) => controller.handleModelChanged(modelId));
    }

    handleConversationPersisted(conversationId: string): void {
        this.#session.withTokenCounter((controller) => controller.handleConversationPersisted(conversationId));
    }

    noteConversationContentCommitted(): void {
        this.#session.withTokenCounter((controller) => controller.noteConversationContentCommitted());
    }

    syncTokenCounterEnabledState(): void {
        this.#session.withTokenCounter((controller) => controller.syncEnabledState());
    }

    cancelConversationInput(conversationId: string, inputId: string): Promise<void> {
        return this.#dependencies.runtime.turnRuntime.requireConversationInputs().cancelPrompt(conversationId, inputId);
    }

    async resolveAskUserPrompt(conversationId: string, taskId: string, action: 'submit' | 'cancel'): Promise<void> {
        await resolveAskUserPromptForConstruction(this.#promptResolutionHost(), conversationId, taskId, action);
    }

    async resolveSecretPrompt(conversationId: string, taskId: string, request: SecretPromptInteractionResolutionRequest): Promise<void> {
        await resolveSecretPromptForConstruction(this.#promptResolutionHost(), conversationId, taskId, request);
    }

    async resolveToolApprovalPrompt(conversationId: string, taskId: string, action: 'approve' | 'deny'): Promise<void> {
        await resolveToolApprovalPromptForConstruction(this.#promptResolutionHost(), conversationId, taskId, action);
    }

    handleInputHistoryNavigation(input: HTMLTextAreaElement, direction: 'up' | 'down'): boolean {
        this.#promptHistory.schedule(input, direction);
        return true;
    }

    noteDraftChanged(value: string): void {
        this.#promptHistory.noteExternalEdit();
        this.#dependencies.runtime.composerSurface.requireSoaiLinkResolution().noteDisplayedTextChanged(value);
        this.#session.withTokenCounter((controller) => controller.noteDraftChanged(value));
        this.#session.draft?.notifyComposerChanged();
    }

    refreshTokenCounterPreview(): void {
        this.#session.withTokenCounter((controller) => controller.noteRequestParametersChanged());
    }

    handleConversationRendered(conversationId: string | null): void {
        this.#promptHistory.invalidate();
        this.#session.handleConversationRendered(conversationId);
        this.#session.withTokenCounter((controller) => controller.handleConversationRendered(conversationId));
    }

    initializeElicitation(session: ChatElicitationSession): void {
        this.#session.initializeElicitation(session);
    }

    hasElicitation(): boolean {
        return this.#session.hasElicitation;
    }

    disposeElicitation(): void {
        this.#session.disposeElicitation();
    }

    focusInteraction(conversationId: string, interactionType: 'ask_user' | 'tool_approval' | 'vault_secret_request', taskId: string): void {
        this.#session.requireElicitation().focusInteraction(conversationId, interactionType, taskId);
    }

    initializeDraft(manager: ChatComposerDraftManager): void {
        this.#session.initializeDraft(manager);
    }

    draftManager(): ChatComposerDraftManager | null {
        return this.#session.draft;
    }

    async flushDraft(reason: string, options: ComposerDraftFlushOptions = {}): Promise<void> {
        await this.#session.flushDraft(reason, options);
    }

    disposeDraft(): void {
        this.#promptHistory.invalidate();
        this.#session.disposeDraft();
    }

    #applyPromptHistoryValue(input: HTMLTextAreaElement, value: string): void {
        this.#dependencies.runtime.composerSurface.requireSoaiLinkResolution().resetToLiteral(value);
        this.#dependencies.input.setUIValue(input, value, { attribute: 'value' });
        refreshChatInputUiState(this.#dependencies.input, input);
        this.noteDraftChanged(value);
        input.setSelectionRange(value.length, value.length);
    }

    applyParameterValueFromElement(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): void {
        this.#dependencies.runtime.configurationRuntime.requireParameters().applyParameterValueFromElement(element);
        this.#syncTokenCounterForParameterChange();
    }

    insertTranscription(text: string): void {
        insertTranscription(this.#inputUiHost(), this.#dependencies.input.getChatInput(), text, (value) => this.noteDraftChanged(value));
    }

    insertTextAtCaret(text: string, mode: 'inline' | 'block'): void {
        const input = this.#dependencies.input.getChatInput();
        if (!(input instanceof HTMLTextAreaElement)) throw new TypeError('Chat input must be a textarea element');
        const value = input.value;
        const selectionStart = input.selectionStart;
        const selectionEnd = input.selectionEnd;
        const before = value.slice(0, selectionStart);
        const after = value.slice(selectionEnd);
        const hasSelection = selectionStart !== selectionEnd;
        const prefix = mode === 'block' && !hasSelection && before.length > 0 && !before.endsWith('\n') ? '\n\n' : '';
        const suffix = mode === 'block' && !hasSelection && after.length > 0 && !after.startsWith('\n') ? '\n\n' : '';
        const nextValue = `${before}${prefix}${text}${suffix}${after}`;
        const nextCaret = before.length + prefix.length + text.length;
        this.#dependencies.input.setUIValue(input, nextValue, { attribute: 'value' });
        input.focus();
        input.setSelectionRange(nextCaret, nextCaret);
        refreshChatInputUiState(this.#dependencies.input, input);
        this.noteDraftChanged(nextValue);
    }

    resizeInput(textarea: Element): void {
        this.#dependencies.input.resizeChatInput(textarea);
    }

    updateEmptyStateInputHint(): void {
        this.#dependencies.input.updateEmptyStateInputHint();
    }

    updateInputState(): void {
        this.#dependencies.input.updateInputState();
    }

    applyInputActionVisibility(): void {
        const dependencies = this.#dependencies;
        applyInputActionVisibilityLifecycle({
            conversationState: dependencies.state.conversationState,
            settings: dependencies.state.settings,
            taskScope: dependencies.sessions.taskScope,
            presentation: dependencies.sessions.presentation,
            conversationView: dependencies.sessions.conversationView,
            voiceSession: dependencies.sessions.voiceSession,
            turnRuntime: dependencies.runtime.turnRuntime,
            services: dependencies.page.services,
            pageElements: dependencies.page.pageElements,
            pageDom: dependencies.page.pageDom,
            dom: dependencies.platform.dom,
            syncTokenCounterEnabledState: () => this.syncTokenCounterEnabledState()
        });
    }

    async toggleTools(): Promise<void> {
        await handleToggleToolsForPage({
            settings: this.#dependencies.state.settings,
            conversationView: this.#dependencies.sessions.conversationView,
            syncToolsEnabledToConversation: (enabled) => this.syncToolsEnabled(enabled)
        });
    }

    syncToolsEnabled(enabled: boolean): Promise<void> {
        return syncToolsEnabledToConversation(this.#toolsSyncHost(), enabled);
    }

    syncToolApprovalRequired(required: boolean): Promise<void> {
        return syncToolApprovalRequiredToConversation(this.#toolsSyncHost(), required);
    }

    persistParameters(): void {
        persistParametersToConversation({
            conversationRuntime: this.#dependencies.runtime.conversationRuntime,
            settings: this.#dependencies.state.settings,
            taskScope: this.#dependencies.sessions.taskScope,
            conversationView: this.#dependencies.sessions.conversationView
        });
    }

    clearInput(): void {
        const input = this.#dependencies.input.getChatInput();
        if (!input) return;
        this.#dependencies.input.setUIValue(input, '', { attribute: 'value' });
        this.#dependencies.input.resizeChatInput(input);
        this.#dependencies.input.updateEmptyStateInputHint();
        this.noteDraftChanged('');
    }

    #syncTokenCounterForParameterChange(): void {
        this.#session.withTokenCounter((controller) => {
            controller.syncEnabledState();
            controller.noteRequestParametersChanged();
        });
    }

    #inputUiHost(): Parameters<typeof insertTranscription>[0] {
        return {
            setUIValue: (target: Element, value: string, options?: { attribute?: string }) => this.#dependencies.input.setUIValue(target, value, options),
            resizeChatInput: (textarea: Element) => this.#dependencies.input.resizeChatInput(textarea),
            updateInputState: () => this.#dependencies.input.updateInputState(),
            updateEmptyStateInputHint: () => this.#dependencies.input.updateEmptyStateInputHint()
        };
    }

    #toolsSyncHost(): SyncToolsEnabledHost {
        return {
            conversationRuntime: this.#dependencies.runtime.conversationRuntime,
            composerSurface: this.#dependencies.runtime.composerSurface,
            preferences: this.#dependencies.sessions.preferences,
            composer: this,
            taskScope: this.#dependencies.sessions.taskScope,
            conversationView: this.#dependencies.sessions.conversationView,
            api: this.#dependencies.platform.api,
            applyInputActionVisibility: () => this.applyInputActionVisibility()
        };
    }

    #promptResolutionHost(): Parameters<typeof resolveAskUserPromptForConstruction>[0] & Parameters<typeof resolveSecretPromptForConstruction>[0] & Parameters<typeof resolveToolApprovalPromptForConstruction>[0] {
        return {
            elicitation: this.#session.requireElicitation(),
            updateInputState: () => this.#dependencies.input.updateInputState(),
            pageDom: this.#dependencies.page.pageDom,
            feedback: this.#dependencies.page.feedback
        };
    }
}

export { ChatComposerController };
export type { ChatComposerContract, ChatComposerDependencies, ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/contracts.ts';

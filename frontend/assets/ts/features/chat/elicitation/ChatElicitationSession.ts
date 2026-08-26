/* SoAI - Chat MCP elicitation session ownership [frontend/assets/ts/features/chat/elicitation/ChatElicitationSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { OnceGuard } from '@core/concurrency/Once.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { consumeNotificationAttentionIntent } from '@core/notifications/attentionIntent.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { TaskCompleteEvent, TaskCreatedEvent } from '@core/realtime/eventcontracts/taskContracts.ts';
import type { AskUserInteractionResolutionRequest, ConversationAttentionRenderedRequest, ConversationInteractionResolutionResponse, ConversationPendingInteractionResponse, SecretPromptInteractionResolutionRequest, ToolApprovalInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { AskUserPrompt } from '@features/chat/askuser/askUserModels.ts';
import { extractTaskCompleteId, parseMcpElicitationTaskCreatedEvent, type McpElicitationInteractionType } from '@features/chat/elicitation/mcpElicitationRealtimeGuards.ts';
import type { SecretPrompt } from '@features/chat/secretprompt/secretPromptModels.ts';
import type { ToolApprovalPrompt } from '@features/chat/toolapproval/toolApprovalModels.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ElicitationType = 'askUser' | 'secretPrompt' | 'toolApproval';
type ElicitationPrompt = AskUserPrompt | SecretPrompt | ToolApprovalPrompt;
type PromptWithAttention = ElicitationPrompt & { taskId: string; notificationId: string | null };

interface ElicitationApi<TResolutionRequest> {
    pending(conversationId: string): Promise<ConversationPendingInteractionResponse>;
    resolve(conversationId: string, taskId: string, request: TResolutionRequest): Promise<ConversationInteractionResolutionResponse>;
    acknowledgeRendered(conversationId: string, request: ConversationAttentionRenderedRequest): Promise<void>;
}

interface ElicitationChannel<TPrompt extends PromptWithAttention, TResolutionRequest> {
    type: ElicitationType;
    interactionType: McpElicitationInteractionType;
    previewSelector: string;
    api: ElicitationApi<TResolutionRequest>;
    parse(response: ConversationPendingInteractionResponse): { conversationId: string; prompt: TPrompt | null } | null;
    build(prompt: TPrompt): TrustedHtml;
    focus(container: Element | null): void;
    syncFailureMessage: string;
    taskCreatedFailureMessage: string;
    prompts: Map<string, TPrompt | null>;
    generations: Map<string, number>;
    acknowledgedTaskIds: Set<string>;
    focusedTaskIds: Set<string>;
}

interface ChatElicitationSessionDependencies {
    askUser: Omit<ElicitationChannel<AskUserPrompt, AskUserInteractionResolutionRequest>, 'prompts' | 'generations' | 'acknowledgedTaskIds' | 'focusedTaskIds'>;
    secretPrompt: Omit<ElicitationChannel<SecretPrompt, SecretPromptInteractionResolutionRequest>, 'prompts' | 'generations' | 'acknowledgedTaskIds' | 'focusedTaskIds'>;
    toolApproval: Omit<ElicitationChannel<ToolApprovalPrompt, ToolApprovalInteractionResolutionRequest>, 'prompts' | 'generations' | 'acknowledgedTaskIds' | 'focusedTaskIds'>;
    getCurrentConversationId(): string | null;
    canAcknowledgePrompt(conversationId: string): boolean;
    optionalUI(selector: string): Element | null;
    updatePreview(type: ElicitationType, markup: TrustedHtml | null): void;
    postRender(container: Element | null): void;
    logWarning(message: string, error: Error): void;
    subscribeTaskCreated(listener: (event: TaskCreatedEvent) => void): () => void;
    subscribeTaskComplete(listener: (event: TaskCompleteEvent) => void): () => void;
}

const createChannel = <TPrompt extends PromptWithAttention, TResolutionRequest>(channel: Omit<ElicitationChannel<TPrompt, TResolutionRequest>, 'prompts' | 'generations' | 'acknowledgedTaskIds' | 'focusedTaskIds'>): ElicitationChannel<TPrompt, TResolutionRequest> => ({
    ...channel,
    prompts: new Map(),
    generations: new Map(),
    acknowledgedTaskIds: new Set(),
    focusedTaskIds: new Set()
});

class ChatElicitationSession {
    readonly #dependencies: ChatElicitationSessionDependencies;
    readonly #askUser: ElicitationChannel<AskUserPrompt, AskUserInteractionResolutionRequest>;
    readonly #secretPrompt: ElicitationChannel<SecretPrompt, SecretPromptInteractionResolutionRequest>;
    readonly #toolApproval: ElicitationChannel<ToolApprovalPrompt, ToolApprovalInteractionResolutionRequest>;
    readonly #initializeOnce = new OnceGuard();
    #disposed = false;
    #lastRenderedConversationId: string | null = null;
    #unsubscribeTaskCreated: (() => void) | null = null;
    #unsubscribeTaskComplete: (() => void) | null = null;
    #requestedFocus: { conversationId: string; interactionType: McpElicitationInteractionType; taskId: string } | null = null;

    constructor(dependencies: ChatElicitationSessionDependencies) {
        this.#dependencies = dependencies;
        this.#askUser = createChannel(dependencies.askUser);
        this.#secretPrompt = createChannel(dependencies.secretPrompt);
        this.#toolApproval = createChannel(dependencies.toolApproval);
    }

    ensureInitialized(): void {
        if (this.#disposed) return;
        this.#initializeOnce.run(() => {
            this.#unsubscribeTaskCreated = this.#dependencies.subscribeTaskCreated((event) => this.#handleTaskCreated(event));
            this.#unsubscribeTaskComplete = this.#dependencies.subscribeTaskComplete((event) => this.#handleTaskComplete(event));
        });
    }

    handleConversationRendered(conversationId: string | null): void {
        this.ensureInitialized();
        if (this.#disposed) return;
        const normalized = normalizeConversationId(conversationId);
        if (!normalized) {
            this.#lastRenderedConversationId = null;
            this.#clearPreviews();
            return;
        }
        if (this.#lastRenderedConversationId === normalized) {
            this.#render(this.#askUser, normalized);
            this.#render(this.#secretPrompt, normalized);
            this.#render(this.#toolApproval, normalized);
            return;
        }
        this.#lastRenderedConversationId = normalized;
        this.#clearPreviews();
        this.#syncAfterConversationRender(this.#askUser, normalized);
        this.#syncAfterConversationRender(this.#secretPrompt, normalized);
        this.#syncAfterConversationRender(this.#toolApproval, normalized);
    }

    getAskUserPrompt(conversationId: string): AskUserPrompt | null {
        return this.#getPrompt(this.#askUser, conversationId);
    }
    getSecretPrompt(conversationId: string): SecretPrompt | null {
        return this.#getPrompt(this.#secretPrompt, conversationId);
    }
    getToolApprovalPrompt(conversationId: string): ToolApprovalPrompt | null {
        return this.#getPrompt(this.#toolApproval, conversationId);
    }
    resolveAskUser(conversationId: string, taskId: string, request: AskUserInteractionResolutionRequest): Promise<void> {
        return this.#resolve(this.#askUser, conversationId, taskId, request);
    }
    resolveSecretPrompt(conversationId: string, taskId: string, request: SecretPromptInteractionResolutionRequest): Promise<void> {
        return this.#resolve(this.#secretPrompt, conversationId, taskId, request);
    }
    resolveToolApproval(conversationId: string, taskId: string, request: ToolApprovalInteractionResolutionRequest): Promise<void> {
        return this.#resolve(this.#toolApproval, conversationId, taskId, request);
    }
    focusInteraction(conversationId: string, interactionType: McpElicitationInteractionType, taskId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedTaskId = taskId.trim();
        if (!normalizedConversationId || !normalizedTaskId) return;
        this.#requestedFocus = { conversationId: normalizedConversationId, interactionType, taskId: normalizedTaskId };
        if (interactionType === 'ask_user') {
            this.#render(this.#askUser, normalizedConversationId);
        } else if (interactionType === 'vault_secret_request') {
            this.#render(this.#secretPrompt, normalizedConversationId);
        } else {
            this.#render(this.#toolApproval, normalizedConversationId);
        }
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#initializeOnce.dispose();
        this.#unsubscribeTaskCreated?.();
        this.#unsubscribeTaskComplete?.();
        this.#unsubscribeTaskCreated = null;
        this.#unsubscribeTaskComplete = null;
        this.#resetChannel(this.#askUser);
        this.#resetChannel(this.#secretPrompt);
        this.#resetChannel(this.#toolApproval);
        this.#lastRenderedConversationId = null;
        this.#requestedFocus = null;
        this.#clearPreviews();
    }

    async #sync<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string): Promise<void> {
        const generation = (channel.generations.get(conversationId) ?? 0) + 1;
        channel.generations.set(conversationId, generation);
        const response = await channel.api.pending(conversationId);
        if (this.#disposed || channel.generations.get(conversationId) !== generation) return;
        const parsed = channel.parse(response);
        if (!parsed || parsed.conversationId !== conversationId) return;
        channel.prompts.set(conversationId, parsed.prompt);
        this.#render(channel, conversationId);
    }

    #syncAfterConversationRender<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string): void {
        void this.#sync(channel, conversationId).catch((error) => this.#dependencies.logWarning(channel.syncFailureMessage, ensureError(error)));
    }

    #render<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string): void {
        if (this.#disposed || normalizeConversationId(this.#dependencies.getCurrentConversationId()) !== conversationId) return;
        const prompt = channel.prompts.get(conversationId) ?? null;
        if (!prompt) {
            this.#dependencies.updatePreview(channel.type, null);
            return;
        }
        this.#dependencies.updatePreview(channel.type, channel.build(prompt));
        const container = this.#dependencies.optionalUI(channel.previewSelector);
        this.#dependencies.postRender(container);
        const canAcknowledge = this.#dependencies.canAcknowledgePrompt(conversationId);
        const attentionMatches = prompt.notificationId ? consumeNotificationAttentionIntent({ conversationId, notificationId: prompt.notificationId }) : false;
        const requestedFocus = this.#requestedFocus;
        const focusMatches = requestedFocus?.conversationId === conversationId && requestedFocus.interactionType === channel.interactionType && requestedFocus.taskId === prompt.taskId;
        if (focusMatches) {
            this.#requestedFocus = null;
            channel.focusedTaskIds.add(prompt.taskId);
            channel.focus(container);
        } else if (canAcknowledge && (attentionMatches || !channel.focusedTaskIds.has(prompt.taskId))) {
            channel.focusedTaskIds.add(prompt.taskId);
            channel.focus(container);
        }
        if (canAcknowledge && prompt.notificationId && !channel.acknowledgedTaskIds.has(prompt.taskId)) {
            channel.acknowledgedTaskIds.add(prompt.taskId);
            void channel.api.acknowledgeRendered(conversationId, { interactionType: channel.interactionType, taskId: prompt.taskId, notificationId: prompt.notificationId }).catch((error) => {
                channel.acknowledgedTaskIds.delete(prompt.taskId);
                this.#dependencies.logWarning('Failed to acknowledge rendered elicitation prompt', ensureError(error));
            });
        }
    }

    async #resolve<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string, taskId: string, request: TResolutionRequest): Promise<void> {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedTaskId = taskId.trim();
        if (!normalizedConversationId || !normalizedTaskId || this.#disposed) return;
        channel.generations.set(normalizedConversationId, (channel.generations.get(normalizedConversationId) ?? 0) + 1);
        await channel.api.resolve(normalizedConversationId, normalizedTaskId, request);
        channel.acknowledgedTaskIds.delete(normalizedTaskId);
        channel.focusedTaskIds.delete(normalizedTaskId);
        channel.prompts.set(normalizedConversationId, null);
        this.#render(channel, normalizedConversationId);
    }

    #handleTaskCreated(event: TaskCreatedEvent): void {
        if (this.#disposed) return;
        this.#syncCreatedChannel(this.#askUser, event);
        this.#syncCreatedChannel(this.#secretPrompt, event);
        this.#syncCreatedChannel(this.#toolApproval, event);
    }

    #syncCreatedChannel<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, event: TaskCreatedEvent): void {
        const created = parseMcpElicitationTaskCreatedEvent(event, channel.interactionType);
        const currentConversationId = normalizeConversationId(this.#dependencies.getCurrentConversationId());
        if (!created || !currentConversationId || currentConversationId !== created.conversationId) return;
        void this.#sync(channel, created.conversationId).catch((error) => this.#dependencies.logWarning(channel.taskCreatedFailureMessage, ensureError(error)));
    }

    #handleTaskComplete(event: TaskCompleteEvent): void {
        if (this.#disposed) return;
        const taskId = extractTaskCompleteId(event);
        const conversationId = normalizeConversationId(this.#dependencies.getCurrentConversationId());
        if (!taskId || !conversationId) return;
        this.#completeChannel(this.#askUser, conversationId, taskId);
        this.#completeChannel(this.#secretPrompt, conversationId, taskId);
        this.#completeChannel(this.#toolApproval, conversationId, taskId);
    }

    #completeChannel<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string, taskId: string): void {
        if (channel.prompts.get(conversationId)?.taskId !== taskId) return;
        channel.acknowledgedTaskIds.delete(taskId);
        channel.focusedTaskIds.delete(taskId);
        channel.prompts.set(conversationId, null);
        this.#render(channel, conversationId);
    }

    #getPrompt<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>, conversationId: string): TPrompt | null {
        const normalized = normalizeConversationId(conversationId);
        return normalized ? (channel.prompts.get(normalized) ?? null) : null;
    }

    #resetChannel<TPrompt extends PromptWithAttention, TResolutionRequest>(channel: ElicitationChannel<TPrompt, TResolutionRequest>): void {
        channel.prompts.clear();
        channel.generations.clear();
        channel.acknowledgedTaskIds.clear();
        channel.focusedTaskIds.clear();
    }

    #clearPreviews(): void {
        this.#dependencies.updatePreview('askUser', null);
        this.#dependencies.updatePreview('secretPrompt', null);
        this.#dependencies.updatePreview('toolApproval', null);
    }
}

export { ChatElicitationSession };
export type { ChatElicitationSessionDependencies, ElicitationApi, ElicitationChannel, ElicitationType };

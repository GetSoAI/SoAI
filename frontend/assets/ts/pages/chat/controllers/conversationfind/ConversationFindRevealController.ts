/* SoAI - Latest desired conversation hit and bounded canonical reveal [frontend/assets/ts/pages/chat/controllers/conversationfind/ConversationFindRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { isAbortError, raceWithAbortSignal, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { analyzeConversationProjection, resolveMessageDomId, type Conversation, type ConversationFindEntry, type ConversationFindTarget, type LoadConversationMessagesOptions, type MountedConversationFindIndex } from '@features/chat/public.ts';
import type { ChatConcurrencyController } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';
import type { ChatComparisonTurnNavigationController } from '@pages/chat/widgets/comparisonturn/ChatComparisonTurnNavigationController.ts';
import type { ConversationFindSearchController } from '@pages/chat/controllers/conversationfind/ConversationFindSearchController.ts';

type ConversationFindRevealStatus = 'loading' | 'editing' | 'missing' | 'timeout' | 'error' | null;

interface ConversationFindRevealDependencies {
    search: ConversationFindSearchController;
    concurrency: ChatConcurrencyController;
    resources: Pick<ResourceTracker, 'setTimeout' | 'clearTimer'>;
    comparison: ChatComparisonTurnNavigationController;
    mounted: MountedConversationFindIndex;
    root: HTMLElement;
    current(): Conversation | null;
    hasModal(): boolean;
    isEditing(): boolean;
    prepareScroll(): () => void;
    load(conversationId: string, options: LoadConversationMessagesOptions): Promise<void>;
    render(canCommit: () => boolean): Promise<void>;
    isWindowRendered(history: NonNullable<Conversation['history']>): boolean;
    refreshMounted(signal: AbortSignal): Promise<void>;
    move(range: Range, isCurrent: () => boolean, signal: AbortSignal): Promise<void>;
    recheckEdges(): void;
    runTask(operationId: string, task: () => Promise<void>): void;
    onStatus(status: ConversationFindRevealStatus): void;
    reportFailure(error: Error): void;
}

class ConversationFindRevealController {
    readonly #dependencies: ConversationFindRevealDependencies;
    readonly #requests = new LatestRequestController();
    #desired: { target: ConversationFindTarget; generation: number } | null = null;
    #running = false;
    #status: ConversationFindRevealStatus = null;

    constructor(dependencies: ConversationFindRevealDependencies) {
        this.#dependencies = dependencies;
    }

    #setStatus(status: ConversationFindRevealStatus): void {
        if (status === this.#status) return;
        this.#status = status;
        this.#dependencies.onStatus(status);
    }

    cancel(): void {
        this.#desired = null;
        this.#requests.invalidate();
        this.#dependencies.concurrency.cancelMessageWindowReveal();
        this.#setStatus(null);
    }

    reveal(target: ConversationFindTarget): void {
        this.#desired = { target, generation: this.#dependencies.search.generation };
        this.#requests.invalidate();
        this.#dependencies.concurrency.cancelMessageWindowReveal();
        if (this.#running) return;
        this.#running = true;
        this.#dependencies.runTask('chat:find:reveal', async () => {
            try {
                while (this.#desired !== null) {
                    const desired = this.#desired;
                    await this.#requests.runLatest(async (request) => {
                        await this.#reveal(desired, request.signal, () => request.isCurrent() && this.#desired === desired && this.#dependencies.search.isCurrent(desired.generation));
                    });
                    if (this.#desired === desired) this.#desired = null;
                }
            } finally {
                this.#running = false;
            }
        });
    }

    async #reveal(desired: { target: ConversationFindTarget; generation: number }, requestSignal: AbortSignal, ownsRequest: () => boolean): Promise<void> {
        const dependencies = this.#dependencies;
        const conversation = dependencies.current();
        if (!conversation || !ownsRequest() || dependencies.hasModal()) return;
        const deadlineAt = monotonicMs() + 30_000;
        const deadline = new AbortController();
        const timer = dependencies.resources.setTimeout(() => deadline.abort(), 30_000);
        const intent = dependencies.concurrency.claimMessageWindowReveal();
        let appliedHistory: Conversation['history'] = undefined;
        let rollbackWindow: (() => void) | null = null;
        const rollback = (): void => {
            rollbackWindow?.();
            rollbackWindow = null;
        };
        const cancellationSignals = [requestSignal, intent.signal, deadline.signal];
        for (const signal of cancellationSignals) signal.addEventListener('abort', rollback, { once: true });
        const scrollScope: { release: (() => void) | null } = { release: null };
        const isCurrent = (): boolean => ownsRequest() && intent.isCurrent() && !deadline.signal.aborted && monotonicMs() < deadlineAt && dependencies.current() === conversation && !dependencies.hasModal();
        const canReplaceWindow = (): boolean => isCurrent() && !dependencies.isEditing();
        try {
            this.#setStatus('loading');
            await runWithAbortSignalScope([requestSignal, intent.signal, deadline.signal], async (signal) => {
                const work = new SearchWorkBudget(dependencies.root.ownerDocument.defaultView, signal);
                for (let attempt = 0; attempt < 2; attempt += 1) {
                    if (!isCurrent()) return;
                    const selected = dependencies.search.snapshot.target ?? desired.target;
                    const entry = dependencies.search.snapshot.index.entries.find((candidate) => candidate.messageId === selected.messageId);
                    if (!entry) break;
                    if (dependencies.isEditing() && dependencies.mounted.body(entry.messageId) === null) {
                        this.#setStatus('editing');
                        return;
                    }
                    scrollScope.release ??= dependencies.prepareScroll();
                    let requiresRender = dependencies.mounted.body(entry.messageId) === null;
                    if (!conversation.messages.some((message, index) => resolveMessageDomId(message, index) === entry.messageId)) {
                        const loaded = await this.#loadTarget(conversation, entry, signal, canReplaceWindow, (history, previousWindow) => {
                            appliedHistory = history;
                            const appliedMessages = conversation.messages;
                            const appliedEntries = [...appliedMessages];
                            rollbackWindow = () => {
                                if (dependencies.isWindowRendered(history) || conversation.history !== history || conversation.messages !== appliedMessages || appliedMessages.length !== appliedEntries.length || appliedMessages.some((message, index) => message !== appliedEntries[index])) return;
                                conversation.messages = previousWindow.messages;
                                if (previousWindow.history === undefined) delete conversation.history;
                                else conversation.history = previousWindow.history;
                                if (previousWindow.messagesHydrated === undefined) delete conversation.messagesHydrated;
                                else conversation.messagesHydrated = previousWindow.messagesHydrated;
                            };
                            if (!isCurrent()) rollback();
                        });
                        if (!isCurrent()) return;
                        if (!loaded || appliedHistory === undefined || conversation.history !== appliedHistory) {
                            if (dependencies.isEditing()) this.#setStatus('editing');
                            else this.#setStatus('missing');
                            return;
                        }
                    }
                    const identity = entry.comparison;
                    if (identity !== null) {
                        const currentVariant = dependencies.comparison.resolveActiveVariantIndexByAssistantTurnTimestamp().get(identity.assistantTurnTimestamp) ?? 0;
                        if (currentVariant !== identity.modelVariantIndex) {
                            if (dependencies.isEditing()) {
                                this.#setStatus('editing');
                                return;
                            }
                            const analysis = analyzeConversationProjection(conversation, { isCurrentStreaming: false, activeComparisonRun: null, activeStreamIdentity: null, isMessagePendingDeletion: () => false });
                            if (!dependencies.comparison.showVariant(analysis, identity.assistantTurnTimestamp, identity.modelVariantIndex)) break;
                            requiresRender = true;
                        }
                    }
                    if (requiresRender) {
                        await work.checkpoint(true);
                        if (!canReplaceWindow()) {
                            if (dependencies.isEditing()) this.#setStatus('editing');
                            return;
                        }
                        const renderingHistory = conversation.history;
                        await dependencies.render(canReplaceWindow);
                        if (!isCurrent() || conversation.history !== renderingHistory) return;
                        await work.checkpoint(true);
                        if (!isCurrent()) return;
                    }
                    if (identity !== null) {
                        const settled = await dependencies.comparison.waitForVariantSettled(dependencies.root, identity.assistantTurnTimestamp, identity.modelVariantIndex, signal, Math.max(0, deadlineAt - monotonicMs()));
                        if (!isCurrent() || !settled) return;
                    }
                    await dependencies.refreshMounted(signal);
                    if (!isCurrent()) return;
                    const target = dependencies.search.snapshot.target;
                    if (!target) break;
                    const range = await dependencies.mounted.range(target, signal);
                    if (!isCurrent()) return;
                    if (range !== null) {
                        await dependencies.move(range, isCurrent, signal);
                        if (!isCurrent()) return;
                        this.#setStatus(null);
                        return;
                    }
                    if (dependencies.isEditing()) {
                        this.#setStatus('editing');
                        return;
                    }
                    if (attempt === 0) {
                        await raceWithAbortSignal(dependencies.search.search(Math.max(0, deadlineAt - monotonicMs())), signal);
                        if (!isCurrent()) return;
                    }
                }
                if (isCurrent()) this.#setStatus('missing');
            });
        } catch (error) {
            if (ownsRequest() && deadline.signal.aborted) this.#setStatus('timeout');
            else if (ownsRequest() && !isAbortError(error)) {
                this.#setStatus('error');
                dependencies.reportFailure(ensureError(error));
            }
        } finally {
            rollback();
            for (const signal of cancellationSignals) signal.removeEventListener('abort', rollback);
            scrollScope.release?.();
            dependencies.resources.clearTimer(timer);
            if (ownsRequest() && deadline.signal.aborted) this.#setStatus('timeout');
            else if (ownsRequest() && this.#status === 'loading') this.#setStatus(null);
            if (intent.release()) dependencies.recheckEdges();
        }
    }

    async #loadTarget(conversation: Conversation, entry: ConversationFindEntry, signal: AbortSignal, isCurrent: () => boolean, onApplied: NonNullable<LoadConversationMessagesOptions['onApplied']>): Promise<boolean> {
        const cursor = entry.cursor;
        if (cursor === null || !isCurrent()) return false;
        let applied = false;
        await this.#dependencies.load(conversation.id, {
            direction: 'around',
            anchor: cursor,
            limit: 25,
            force: true,
            signal,
            isCurrentOperation: isCurrent,
            onApplied: (history, previousWindow) => {
                applied = true;
                onApplied(history, previousWindow);
            }
        });
        return applied && isCurrent() && conversation.messages.some((message) => message.id === cursor.id && message.timestamp === cursor.createdAtMs);
    }
}

export { ConversationFindRevealController };
export type { ConversationFindRevealDependencies, ConversationFindRevealStatus };

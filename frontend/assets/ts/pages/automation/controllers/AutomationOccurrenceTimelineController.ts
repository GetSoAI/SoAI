/* SoAI - Automation occurrence plan and todo timeline with live updates [frontend/assets/ts/pages/automation/controllers/AutomationOccurrenceTimelineController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { dom } from '@core/dom/dom.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { requestAgentPlanSnapshot, requestAgentTodoSnapshot } from '@features/chat/public.ts';

interface AutomationOccurrenceTimelineElements {
    plan: HTMLElement;
    todo: HTMLElement;
    syntaxHighlighter: SyntaxHighlighter;
}

interface TimelineRevisions {
    plan: number;
    todo: number;
}

const formatTodoMarker = (status: AgentPlanStep['status']): string => {
    switch (status) {
        case 'completed':
            return '[x]';
        case 'in_progress':
            return '[*]';
        case 'pending':
            return '[ ]';
    }
};

const renderAutomationHighlightedContent = (element: HTMLElement, content: string, highlighter: SyntaxHighlighter): void => {
    element.textContent = '';
    element.appendChild(highlighter.highlight(content, highlighter.detectLanguage(content)));
    element.classList.remove('is-empty');
};

class AutomationOccurrenceTimelineController {
    readonly #elements: AutomationOccurrenceTimelineElements;
    readonly #session = new SequenceToken();
    readonly #hydration = new LatestRequestController();
    #conversationId: string | null = null;
    #revisions: TimelineRevisions = { plan: -1, todo: -1 };
    #unsubscribe: (() => void) | null = null;

    constructor(elements: AutomationOccurrenceTimelineElements) {
        this.#elements = elements;
    }

    getConversationId(): string | null {
        return this.#conversationId;
    }

    show(conversationId: string | null): void {
        this.clear();
        this.#conversationId = conversationId;
        if (conversationId === null) {
            this.#setMessage(this.#elements.plan, i18n.t('automation.pane.details.timelineUnavailable'), true);
            this.#setMessage(this.#elements.todo, i18n.t('automation.pane.details.timelineUnavailable'), true);
            return;
        }
        const session = this.#session.next();
        this.#setMessage(this.#elements.plan, i18n.t('common.loading'), false);
        this.#setMessage(this.#elements.todo, i18n.t('common.loading'), false);
        this.#unsubscribe = subscribeManagedWebSocketContracts({
            label: 'AutomationOccurrenceTimeline',
            events: [
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                    handler: (): void => {
                        this.#hydration.invalidate();
                        this.#markStale(this.#elements.plan);
                        this.#markStale(this.#elements.todo);
                    }
                }),
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                    handler: (): void => {
                        this.#startHydration(conversationId, session);
                    }
                }),
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.agent.planUpdated,
                    handler: (payload): void => {
                        if (payload.convId === conversationId && this.#session.isActive(session)) this.#applyPlan(payload.revision, payload.markdown);
                    }
                }),
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.agent.todoUpdated,
                    handler: (payload): void => {
                        if (payload.convId === conversationId && this.#session.isActive(session)) this.#applyTodo(payload.revision, payload.todo, payload.explanation);
                    }
                })
            ]
        });
        this.#startHydration(conversationId, session);
    }

    clear(): void {
        this.#hydration.invalidate();
        this.#session.invalidate();
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#conversationId = null;
        this.#revisions = { plan: -1, todo: -1 };
        for (const element of [this.#elements.plan, this.#elements.todo]) {
            delete element.dataset['freshness'];
            delete element.dataset['lastSyncedAtMs'];
        }
        this.#setMessage(this.#elements.plan, i18n.t('automation.pane.details.planEmpty'), true);
        this.#setMessage(this.#elements.todo, i18n.t('automation.pane.details.todoEmpty'), true);
    }

    #startHydration(conversationId: string, session: number): void {
        this.#hydration
            .runLatest(async (run) => {
                const [planResult, todoResult] = await Promise.allSettled([raceWithAbortSignal(requestAgentPlanSnapshot(conversationId, run.signal), run.signal), raceWithAbortSignal(requestAgentTodoSnapshot(conversationId, run.signal), run.signal)]);
                if (!run.isCurrent() || !this.#session.isActive(session)) {
                    return;
                }
                if (planResult.status === 'fulfilled') {
                    this.#applyPlan(planResult.value.revision, planResult.value.markdown);
                } else {
                    errorHandler.warn('AutomationOccurrenceTimelineController', 'Failed to hydrate automation transcript plan', ensureError(planResult.reason), { context: { convId: conversationId } });
                    if (this.#revisions.plan < 0) this.#setMessage(this.#elements.plan, i18n.t('automation.pane.details.timelineUnavailable'), true);
                    this.#markStale(this.#elements.plan);
                }
                if (todoResult.status === 'fulfilled') {
                    this.#applyTodo(todoResult.value.revision, todoResult.value.todo, todoResult.value.explanation);
                } else {
                    errorHandler.warn('AutomationOccurrenceTimelineController', 'Failed to hydrate automation transcript todo', ensureError(todoResult.reason), { context: { convId: conversationId } });
                    if (this.#revisions.todo < 0) this.#setMessage(this.#elements.todo, i18n.t('automation.pane.details.timelineUnavailable'), true);
                    this.#markStale(this.#elements.todo);
                }
            })
            .catch((error) => errorHandler.warn('AutomationOccurrenceTimelineController', 'Timeline recovery failed', ensureError(error)));
    }

    #applyPlan(revision: number, markdown: string | null): void {
        if (revision < this.#revisions.plan) {
            return;
        }
        this.#revisions = { ...this.#revisions, plan: revision };
        this.#elements.plan.dataset['freshness'] = 'current';
        this.#elements.plan.dataset['lastSyncedAtMs'] = String(Date.now());
        if (markdown) {
            renderAutomationHighlightedContent(this.#elements.plan, markdown, this.#elements.syntaxHighlighter);
            return;
        }
        this.#setMessage(this.#elements.plan, i18n.t('automation.pane.details.planEmpty'), true);
    }

    #applyTodo(revision: number, steps: readonly AgentPlanStep[], explanation: string | null): void {
        if (revision < this.#revisions.todo) {
            return;
        }
        this.#revisions = { ...this.#revisions, todo: revision };
        this.#elements.todo.dataset['freshness'] = 'current';
        this.#elements.todo.dataset['lastSyncedAtMs'] = String(Date.now());
        if (steps.length === 0) {
            this.#setMessage(this.#elements.todo, i18n.t('automation.pane.details.todoEmpty'), true);
            return;
        }
        const lines = steps.map((step) => `${formatTodoMarker(step.status)} ${step.step}`);
        renderAutomationHighlightedContent(this.#elements.todo, explanation ? [...lines, '', explanation].join('\n') : lines.join('\n'), this.#elements.syntaxHighlighter);
    }

    #setMessage(element: HTMLElement, message: string, empty: boolean): void {
        element.textContent = message;
        element.classList.toggle('is-empty', empty);
    }

    #markStale(element: HTMLElement): void {
        element.dataset['freshness'] = 'stale';
        if (dom.resolve('[data-timeline-stale]', element)) return;
        const status = document.createElement('p');
        status.dataset['timelineStale'] = '';
        status.setAttribute('role', 'status');
        const lastSyncedAtMs = Number(element.dataset['lastSyncedAtMs']);
        status.textContent = Number.isFinite(lastSyncedAtMs) && lastSyncedAtMs > 0 ? `${i18n.t('automation.toolbar.staleData')} (${i18n.formatDate(new Date(lastSyncedAtMs), { hour: '2-digit', minute: '2-digit', second: '2-digit' })})` : i18n.t('automation.toolbar.staleData');
        element.prepend(status);
    }
}

export { AutomationOccurrenceTimelineController, renderAutomationHighlightedContent };

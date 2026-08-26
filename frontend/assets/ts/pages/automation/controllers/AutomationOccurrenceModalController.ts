/* SoAI - Automation page occurrence modal controller [frontend/assets/ts/pages/automation/controllers/AutomationOccurrenceModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { AUTOMATION_OCCURRENCE_MODAL_ID, type AutomationZone } from '@features/automation/public.ts';
import { requestAgentPlanSnapshot, requestAgentTodoSnapshot } from '@features/chat/public.ts';
import { buildAutomationZoneKeyForZone } from '@pages/automation/contracts/zoneKey.ts';
import { formatAutomationRunWhen } from '@pages/automation/formatting/service.ts';
import { formatAutomationRunStatusLabel, resolveAutomationRunExcerpt, resolveAutomationRunStatusBadgeClass } from '@pages/automation/controllers/automationZoneFormatters.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface AutomationOccurrenceModalControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    syntaxHighlighter: SyntaxHighlighter;
}

class AutomationOccurrenceModalController {
    readonly #dependencies: AutomationOccurrenceModalControllerDependencies;
    readonly #modalId = AUTOMATION_OCCURRENCE_MODAL_ID;
    readonly #modalRoot: HTMLElement;
    readonly #title: HTMLElement;
    readonly #when: HTMLElement;
    readonly #status: HTMLElement;
    readonly #excerpt: HTMLElement;
    readonly #plan: HTMLElement;
    readonly #todo: HTMLElement;
    readonly #deleteRunButton: HTMLButtonElement;
    readonly #openTranscriptButton: HTMLButtonElement;
    readonly #viewTaskButton: HTMLButtonElement;
    #loadSequence = 0;

    constructor(dependencies: AutomationOccurrenceModalControllerDependencies) {
        this.#dependencies = dependencies;
        this.#modalRoot = dependencies.modalPresenter.requireElement(this.#modalId);
        this.#title = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'occurrence-title'), this.#modalRoot);
        this.#when = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'when'), this.#modalRoot);
        this.#status = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'status'), this.#modalRoot);
        this.#excerpt = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'excerpt'), this.#modalRoot);
        this.#plan = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'plan'), this.#modalRoot);
        this.#todo = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'todo'), this.#modalRoot);

        const deleteButton = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'delete-run'), this.#modalRoot);
        if (!(deleteButton instanceof HTMLButtonElement)) {
            throw new Error('Automation occurrence delete button must be a button');
        }
        this.#deleteRunButton = deleteButton;
        const transcriptButton = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'open-transcript'), this.#modalRoot);
        if (!(transcriptButton instanceof HTMLButtonElement)) {
            throw new Error('Automation occurrence transcript button must be a button');
        }
        this.#openTranscriptButton = transcriptButton;
        const viewButton = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'view-task'), this.#modalRoot);
        if (!(viewButton instanceof HTMLButtonElement)) {
            throw new Error('Automation occurrence view task button must be a button');
        }
        this.#viewTaskButton = viewButton;
    }

    #renderHighlightedContent(element: HTMLElement, content: string): void {
        element.textContent = '';
        const language = this.#dependencies.syntaxHighlighter.detectLanguage(content);
        const highlighted = this.#dependencies.syntaxHighlighter.highlight(content, language);
        element.appendChild(highlighted);
    }

    #setTimelineUnavailable(element: HTMLElement): void {
        element.textContent = i18n.t('automation.pane.details.timelineUnavailable');
        element.classList.add('is-empty');
    }

    #renderPlan(markdown: string | null): void {
        if (markdown) {
            this.#renderHighlightedContent(this.#plan, markdown);
            this.#plan.classList.remove('is-empty');
            return;
        }
        this.#plan.textContent = i18n.t('automation.pane.details.planEmpty');
        this.#plan.classList.add('is-empty');
    }

    #renderTodo(todoSteps: AgentPlanStep[], explanation: string | null): void {
        if (todoSteps.length > 0) {
            const lines: string[] = [];
            for (const step of todoSteps) {
                const marker = step.status === 'completed' ? '[x]' : step.status === 'in_progress' ? '[*]' : '[ ]';
                lines.push(`${marker} ${step.step}`);
            }
            if (explanation) {
                lines.push('');
                lines.push(explanation);
            }
            this.#renderHighlightedContent(this.#todo, lines.join('\n'));
            this.#todo.classList.remove('is-empty');
            return;
        }
        this.#todo.textContent = i18n.t('automation.pane.details.todoEmpty');
        this.#todo.classList.add('is-empty');
    }

    open(zone: AutomationZone, calendarSettings: AutomationCalendarSettings): void {
        const loadSequence = (this.#loadSequence += 1);
        this.#title.textContent = zone.title;
        this.#when.textContent = formatAutomationRunWhen(zone.scheduledAtMs, calendarSettings);
        this.#status.textContent = formatAutomationRunStatusLabel(zone.status);
        this.#status.dataset['runStatus'] = zone.status;
        const variant = resolveAutomationRunStatusBadgeClass(zone.status);
        this.#status.classList.remove('status-green', 'status-red', 'status-orange', 'status-grey');
        this.#status.classList.add(variant);
        this.#deleteRunButton.dataset['zoneKey'] = buildAutomationZoneKeyForZone(zone);
        this.#deleteRunButton.disabled = false;
        this.#deleteRunButton.setAttribute('aria-disabled', 'false');

        const excerpt = resolveAutomationRunExcerpt(zone);
        if (excerpt) {
            this.#renderHighlightedContent(this.#excerpt, excerpt);
            this.#excerpt.classList.remove('is-empty');
        } else {
            this.#excerpt.textContent = i18n.t('automation.pane.details.noExcerpt');
            this.#excerpt.classList.add('is-empty');
        }

        const conversationId = zone.convId;
        this.#openTranscriptButton.dataset['conversationId'] = conversationId ?? '';
        this.#openTranscriptButton.disabled = conversationId === null;
        this.#openTranscriptButton.setAttribute('aria-disabled', conversationId === null ? 'true' : 'false');
        this.#viewTaskButton.dataset['automationId'] = zone.automationId;
        this.#viewTaskButton.disabled = false;
        this.#viewTaskButton.setAttribute('aria-disabled', 'false');

        if (conversationId === null) {
            this.#plan.textContent = i18n.t('automation.pane.details.timelineUnavailable');
            this.#plan.classList.add('is-empty');
            this.#todo.textContent = i18n.t('automation.pane.details.timelineUnavailable');
            this.#todo.classList.add('is-empty');
            this.#dependencies.modalPresenter.open(this.#modalId);
            return;
        }

        this.#plan.textContent = i18n.t('common.loading');
        this.#plan.classList.remove('is-empty');
        this.#todo.textContent = i18n.t('common.loading');
        this.#todo.classList.remove('is-empty');
        this.#dependencies.modalPresenter.open(this.#modalId);
        this.#hydrateTimeline(conversationId, loadSequence).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('AutomationOccurrenceModalController', 'Failed to hydrate automation transcript plan/todo', runtimeError, {
                context: { convId: conversationId }
            });
        });
    }

    async #hydrateTimeline(conversationId: string, loadSequence: number): Promise<void> {
        const [planResult, todoResult] = await Promise.allSettled([requestAgentPlanSnapshot(conversationId), requestAgentTodoSnapshot(conversationId)]);
        if (loadSequence !== this.#loadSequence) {
            return;
        }

        if (planResult.status === 'fulfilled') {
            this.#renderPlan(planResult.value.markdown ?? null);
        } else {
            errorHandler.warn('AutomationOccurrenceModalController', 'Failed to hydrate automation transcript plan', ensureError(planResult.reason), {
                context: { convId: conversationId }
            });
            this.#setTimelineUnavailable(this.#plan);
        }

        if (todoResult.status === 'fulfilled') {
            this.#renderTodo(todoResult.value.todo, todoResult.value.explanation);
        } else {
            errorHandler.warn('AutomationOccurrenceModalController', 'Failed to hydrate automation transcript todo', ensureError(todoResult.reason), {
                context: { convId: conversationId }
            });
            this.#setTimelineUnavailable(this.#todo);
        }
    }

    close(): void {
        this.#loadSequence += 1;
        this.#openTranscriptButton.disabled = true;
        this.#openTranscriptButton.setAttribute('aria-disabled', 'true');
        this.#openTranscriptButton.dataset['conversationId'] = '';
        this.#deleteRunButton.disabled = true;
        this.#deleteRunButton.setAttribute('aria-disabled', 'true');
        this.#deleteRunButton.dataset['zoneKey'] = '';
        this.#viewTaskButton.disabled = true;
        this.#viewTaskButton.setAttribute('aria-disabled', 'true');
        this.#viewTaskButton.dataset['automationId'] = '';
        this.#plan.textContent = i18n.t('automation.pane.details.planEmpty');
        this.#plan.classList.add('is-empty');
        this.#todo.textContent = i18n.t('automation.pane.details.todoEmpty');
        this.#todo.classList.add('is-empty');
        this.#dependencies.modalPresenter.close(this.#modalId);
    }

    isOpen(): boolean {
        return this.#dependencies.modalPresenter.isOpen(this.#modalId);
    }
}

export { AutomationOccurrenceModalController };

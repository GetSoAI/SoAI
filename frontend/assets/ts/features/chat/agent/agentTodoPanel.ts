/* SoAI - Chat feature agent todo panel [frontend/assets/ts/features/chat/agent/agentTodoPanel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';

const PLAN_STATUS_RANK: Readonly<Record<AgentPlanStep['status'], number>> = Object.freeze({
    'in_progress': 0,
    pending: 1,
    completed: 2
});

const sortPlanForDisplay = (plan: AgentPlanStep[]): AgentPlanStep[] => {
    return plan
        .map((entry, index) => ({ entry, index, rank: PLAN_STATUS_RANK[entry.status] }))
        .sort((left, right) => left.rank - right.rank || left.index - right.index)
        .map(({ entry }) => entry);
};

interface AgentTodoPanelDependencies {
    escapeHtml(value: string): string;
    getIcon(name: IconName, options?: IconOptions): TrustedHtml;
    hasPlan: boolean;
    planHasUnseenUpdate: boolean;
}

const renderTodoItems = (dependencies: AgentTodoPanelDependencies, todo: AgentPlanStep[]): string => {
    const rows = sortPlanForDisplay(todo)
        .map((entry) => {
            const label = dependencies.escapeHtml(entry.step);
            const statusClass = `agent-todo-item--${entry.status.replace(/_/g, '-')}`;
            return `<li class="agent-todo-item ${statusClass}"><span class="agent-todo-item-led" aria-hidden="true"></span><span class="agent-todo-item-text">${label}</span></li>`;
        })
        .join('');

    const itemsLabel = dependencies.hasPlan ? i18n.t('chat.agent.plan.items') : i18n.t('chat.agent.todo.items');
    return `<ul class="agent-todo-items" aria-label="${dependencies.escapeHtml(itemsLabel)}">${rows}</ul>`;
};

const renderViewPlanButton = (dependencies: AgentTodoPanelDependencies): string => {
    if (!dependencies.hasPlan) {
        return '';
    }
    const viewPlanLabel = dependencies.escapeHtml(i18n.t('chat.agent.plan.viewPlan'));
    const planIcon = renderIconSlot(dependencies.getIcon('plan', { size: 24, strokeWidth: 1.5 }));
    const updateDot = dependencies.planHasUnseenUpdate ? '<span class="agent-todo-plan-update-count" aria-hidden="true"></span>' : '';
    return `<button type="button" class="agent-todo-panel-view-plan ui-button" data-action="chat:view-agent-plan" data-tooltip="${viewPlanLabel}" aria-label="${viewPlanLabel}"><span class="agent-todo-panel-view-plan-icon-wrapper">${planIcon}${updateDot}</span><span>${viewPlanLabel}</span></button>`;
};

const renderPanelHeader = (inputArguments: { dependencies: AgentTodoPanelDependencies; titleText: string; collapsed: boolean; hasSteps: boolean }): string => {
    const { dependencies, titleText, collapsed, hasSteps } = inputArguments;
    const escapedTitle = dependencies.escapeHtml(titleText);

    if (!hasSteps) {
        return `<div class="agent-todo-panel-header">${`<span class="agent-todo-panel-title">${escapedTitle}</span>`}${renderViewPlanButton(dependencies)}</div>`;
    }

    const toggleLabel = dependencies.escapeHtml(dependencies.hasPlan ? (collapsed ? i18n.t('chat.agent.plan.expand') : i18n.t('chat.agent.plan.collapse')) : collapsed ? i18n.t('chat.agent.todo.expand') : i18n.t('chat.agent.todo.collapse'));
    const toggleIcon = dependencies.getIcon(collapsed ? 'chevron-down' : 'chevron-up', { size: 14, strokeWidth: 1.8 }).html;
    const expandedAttr = collapsed ? 'false' : 'true';
    const headerActionAttrs = `data-action="chat:toggle-todo-panel" aria-expanded="${expandedAttr}" data-tooltip="${toggleLabel}" aria-label="${toggleLabel}"`;

    return `<div class="agent-todo-panel-header" ${headerActionAttrs}>` + `<div class="agent-todo-panel-header-toggle" aria-hidden="true"><span class="agent-todo-panel-title">${escapedTitle}</span><span class="agent-todo-panel-toggle-icon" aria-hidden="true">${toggleIcon}</span></div>` + renderViewPlanButton(dependencies) + '</div>';
};

const renderAgentTodoPanel = (dependencies: AgentTodoPanelDependencies, todo: AgentPlanStep[], collapsed: boolean): string => {
    const hasSteps = todo.length > 0;
    const titleText = dependencies.hasPlan ? i18n.t('chat.agent.mode.plan') : i18n.t('chat.agent.todo.title');

    const shouldCollapse = hasSteps ? collapsed : true;
    const panelClass = shouldCollapse ? 'agent-todo-panel agent-todo-panel--collapsed' : 'agent-todo-panel';
    const headerHtml = renderPanelHeader({ dependencies, titleText, collapsed: shouldCollapse, hasSteps });
    const bodyHtml = hasSteps ? `<div class="agent-todo-panel-body">${renderTodoItems(dependencies, todo)}</div>` : '';

    return `<section class="${panelClass}" aria-label="${dependencies.escapeHtml(titleText)}">${headerHtml}${bodyHtml}</section>`;
};

const resolveAgentTodoPanelRenderSignature = (dependencies: AgentTodoPanelDependencies, todo: AgentPlanStep[], collapsed: boolean): string => {
    return JSON.stringify({
        todo,
        collapsed,
        hasPlan: dependencies.hasPlan,
        planHasUnseenUpdate: dependencies.planHasUnseenUpdate
    });
};

const updateAgentTodoPanelElement = (container: HTMLElement, dependencies: AgentTodoPanelDependencies, todo: AgentPlanStep[], collapsed: boolean): void => {
    const previousCollapsed = container.dataset['agentTodoPanelCollapsed'] === 'true';
    const hasPreviousCollapsedState = container.dataset['agentTodoPanelCollapsed'] === 'true' || container.dataset['agentTodoPanelCollapsed'] === 'false';
    const nextSignature = resolveAgentTodoPanelRenderSignature(dependencies, todo, collapsed);
    const hasRenderedPanel = dom.resolve('.agent-todo-panel', container) instanceof HTMLElement;
    if (container.dataset['agentTodoPanelSignature'] !== nextSignature || !hasRenderedPanel) {
        const nextMarkup = renderAgentTodoPanel(dependencies, todo, collapsed);
        const markup = toTrustedUiHtml(nextMarkup);
        dom.setHTML(container, markup, { escape: false });
        container.dataset['agentTodoPanelSignature'] = nextSignature;
    }

    container.dataset['agentTodoPanelCollapsed'] = String(collapsed);

    if (!hasPreviousCollapsedState || previousCollapsed === collapsed) {
        return;
    }

    const panel = dom.resolve('.agent-todo-panel', container);
    if (!(panel instanceof HTMLElement)) {
        return;
    }

    panel.classList.add('agent-todo-panel--no-transition');
    panel.classList.toggle('agent-todo-panel--collapsed', previousCollapsed);
    void panel.offsetHeight;
    panel.classList.remove('agent-todo-panel--no-transition');
    requestAnimationFrame(() => {
        panel.classList.toggle('agent-todo-panel--collapsed', collapsed);
    });
};

export { updateAgentTodoPanelElement };
export type { AgentTodoPanelDependencies };

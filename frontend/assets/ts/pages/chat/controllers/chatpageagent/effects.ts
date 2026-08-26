/* SoAI - Chat page agent effects [frontend/assets/ts/pages/chat/controllers/chatpageagent/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { i18n } from '@core/i18n/index.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { applyAgentModeBorderIndicator, CHAT_ICON_SIZE_SM, resolveAgentMode, resolveAgentModeLabel, updateAgentTodoPanelElement, type Conversation } from '@features/chat/public.ts';
import { applyAuthorityLockedButtonState, resolveAuthorityLockedControlLabel, resolveConversationAuthorityLock, type ConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { removeAgentModePopup, showAgentModePopup } from '@pages/chat/controllers/chatpageagent/agentModePopupController.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

const AGENT_MODE_ICON_MAP: Readonly<Record<AgentMode, IconName>> = Object.freeze({
    chat: 'chat',
    plan: 'tasks',
    execute: 'terminal'
});
const AGENT_TODO_PANEL_CONTAINER_SELECTOR = '#agent-todo-panel-container';
const AGENT_MODE_INDICATOR_GROUP_SELECTOR = '.chat-page-mode-indicator';
const AGENT_PLAN_BAR_TOGGLE_SELECTOR = '.plan-bar-toggle-btn';

interface AgentPlanBarState {
    hasPlan: boolean;
    available: boolean;
    shown: boolean;
}

const resolveAgentPlanBarState = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation | null): AgentPlanBarState => {
    if (conversation === null) {
        return { hasPlan: false, available: false, shown: false };
    }
    const hasPlan = state.canonicalPlanRevision > 0;
    const available = hasPlan || state.canonicalTodo.length > 0;
    return { hasPlan, available, shown: available && host.planBar.isVisible() };
};

const resolveChatInput = (host: ChatPageAgentHost, state: ChatPageAgentState): HTMLTextAreaElement | null => {
    const cached = state.cachedChatInput;
    if (cached && cached.isConnected) {
        return cached;
    }
    const chatInput = host.rendering.getChatInput();
    state.cachedChatInput = chatInput;
    return chatInput;
};

const resolveTodoPanelContainer = (host: ChatPageAgentHost, state: ChatPageAgentState): HTMLElement | null => {
    const cached = state.cachedTodoPanelContainer;
    if (cached && cached.isConnected) {
        return cached;
    }
    const resolved = host.workflow.pageDom.optionalHTMLElement(AGENT_TODO_PANEL_CONTAINER_SELECTOR);
    state.cachedTodoPanelContainer = resolved;
    return resolved;
};

const hasRenderableConversationMessages = (conversation: Conversation | null): boolean => {
    if (!conversation) {
        return false;
    }
    const { messages } = conversation;
    if (!isArray(messages) || messages.length === 0) {
        return false;
    }
    for (const message of messages) {
        if (!message || !isObject(message)) {
            continue;
        }
        if (message['role'] === 'system') {
            continue;
        }
        return true;
    }
    return false;
};

const updateAgentModeBorderIndicator = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation | null): void => {
    const chatInput = resolveChatInput(host, state);
    if (!chatInput) {
        state.lastAppliedAgentMode = null;
        state.lastAppliedAgentModeInput = null;
        removeAgentModePopup(state.agentModePopup);
        return;
    }
    const mode = resolveAgentMode(conversation);
    if (state.lastAppliedAgentMode === mode && state.lastAppliedAgentModeInput === chatInput) {
        showAgentModePopup(state.agentModePopup, chatInput, mode);
        return;
    }
    applyAgentModeBorderIndicator(chatInput, mode);
    showAgentModePopup(state.agentModePopup, chatInput, mode);
    state.lastAppliedAgentMode = mode;
    state.lastAppliedAgentModeInput = chatInput;
};

const syncAgentModeCycleButton = (host: ChatPageAgentHost, button: HTMLButtonElement, conversation: Conversation | null, lock: ConversationAuthorityLock | null): void => {
    const mode = resolveAgentMode(conversation);
    const label = resolveAgentModeLabel(mode);
    const renderSignature = `${mode}|${label}`;
    if (button.dataset['agentModeCycleSignature'] !== renderSignature) {
        button.setAttribute('data-agent-mode', mode);
        const iconSlot = host.workflow.pageDom.optionalHTMLElement('.agent-mode-cycle-icon', button);
        if (iconSlot) {
            host.workflow.pageDom.updateHtml(iconSlot, host.rendering.getCachedIcon(AGENT_MODE_ICON_MAP[mode], CHAT_ICON_SIZE_SM));
        }
        const labelSlot = host.workflow.pageDom.optionalHTMLElement('.agent-mode-cycle-label', button);
        if (labelSlot) {
            labelSlot.textContent = label;
        } else {
            button.textContent = label;
        }
        button.dataset['agentModeCycleSignature'] = renderSignature;
    }
    const cycleTooltip = i18n.t('chat.agent.mode.cycleTooltip');
    applyAuthorityLockedButtonState(button, {
        lock,
        actionLabel: cycleTooltip,
        unlockedAriaLabel: cycleTooltip,
        unlockedTooltip: cycleTooltip,
        unlockedDisabled: false
    });
};

const updateAgentModeCycleButton = (host: ChatPageAgentHost, conversation: Conversation | null, lock: ConversationAuthorityLock | null): void => {
    for (const candidate of host.workflow.pageDom.query('.agent-mode-cycle-btn')) {
        if (candidate instanceof HTMLButtonElement) {
            syncAgentModeCycleButton(host, candidate, conversation, lock);
        }
    }
};

const applyAgentModeIndicatorAuthorityLock = (host: ChatPageAgentHost, indicatorSelect: HTMLSelectElement, lock: ConversationAuthorityLock | null): void => {
    const indicatorGroup = host.workflow.pageDom.optionalHTMLElement(AGENT_MODE_INDICATOR_GROUP_SELECTOR);
    const modeLabel = i18n.t('chat.empty.modeLabel');
    if (lock === null) {
        indicatorSelect.disabled = false;
        indicatorSelect.removeAttribute('aria-disabled');
        indicatorSelect.setAttribute('aria-label', modeLabel);
        if (indicatorGroup) {
            delete indicatorGroup.dataset['settingsAuthorityLock'];
            setTooltipText(indicatorGroup, '');
        }
        return;
    }
    indicatorSelect.disabled = true;
    indicatorSelect.setAttribute('aria-disabled', 'true');
    indicatorSelect.setAttribute('aria-label', resolveAuthorityLockedControlLabel(lock, modeLabel));
    if (indicatorGroup) {
        indicatorGroup.dataset['settingsAuthorityLock'] = lock.authorityType;
        setTooltipText(indicatorGroup, lock.reason);
    }
};

const updateAgentModeIndicator = (host: ChatPageAgentHost, conversation: Conversation | null, lock: ConversationAuthorityLock | null): void => {
    const indicatorSelect = host.workflow.pageDom.optionalHTMLElement('.chat-page-mode-indicator-select');
    if (!indicatorSelect) {
        return;
    }
    if (!(indicatorSelect instanceof HTMLSelectElement)) {
        throw new TypeError('Agent mode indicator must be a select element');
    }
    const mode = resolveAgentMode(conversation);
    if (indicatorSelect.value !== mode) {
        indicatorSelect.value = mode;
    }
    if (indicatorSelect.getAttribute('data-agent-mode') !== mode) {
        indicatorSelect.setAttribute('data-agent-mode', mode);
    }
    applyAgentModeIndicatorAuthorityLock(host, indicatorSelect, lock);
};

const applyAgentTodoPanelVisibility = (host: ChatPageAgentHost, container: HTMLElement, visible: boolean): void => {
    container.dataset['agentTodoPanelVisibility'] = visible ? 'visible' : 'hidden';
    host.workflow.pageDom.updateAttribute(container, 'inert', visible ? null : '');
};

const clearAgentTodoPanel = (host: ChatPageAgentHost, container: HTMLElement): void => {
    if (container.childElementCount > 0 || container.textContent !== '') {
        host.workflow.pageDom.updateHtml(container, '');
    }
    applyAgentTodoPanelVisibility(host, container, false);
    delete container.dataset['agentTodoPanelSignature'];
    delete container.dataset['agentTodoPanelCollapsed'];
};

const updateAgentTodoPanel = (host: ChatPageAgentHost, state: ChatPageAgentState, planBar: AgentPlanBarState): void => {
    const container = resolveTodoPanelContainer(host, state);
    const messageHost = host.rendering.messages;
    if (!container) {
        return;
    }
    if (!planBar.available) {
        clearAgentTodoPanel(host, container);
        return;
    }
    updateAgentTodoPanelElement(
        container,
        {
            escapeHtml: (value) => messageHost.escapeHtml(value),
            getIcon: (iconName, options) => host.rendering.getCachedIcon(iconName, options),
            hasPlan: planBar.hasPlan,
            planHasUnseenUpdate: state.planHasUnseenUpdate
        },
        state.canonicalTodo,
        state.todoPanelCollapsed
    );
    applyAgentTodoPanelVisibility(host, container, planBar.shown);
};

const updatePlanBarToggleButton = (host: ChatPageAgentHost, planBar: AgentPlanBarState): void => {
    const iconName: IconName = planBar.hasPlan ? 'plan' : 'tasks';
    const label = planBar.hasPlan ? i18n.t('chat.header.togglePlanBar') : i18n.t('chat.header.toggleTodoBar');
    const renderSignature = `${iconName}|${label}`;
    for (const candidate of host.workflow.pageDom.query(AGENT_PLAN_BAR_TOGGLE_SELECTOR)) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        host.workflow.pageDom.toggleClass(candidate, 'u-hidden', !planBar.available);
        host.workflow.pageDom.updateAttribute(candidate, 'aria-expanded', planBar.shown ? 'true' : 'false');
        host.workflow.pageDom.updateAttribute(candidate, 'aria-label', label);
        setTooltipText(candidate, label);
        if (candidate.dataset['planBarToggleSignature'] === renderSignature) {
            continue;
        }
        const iconSlot = host.workflow.pageDom.optionalHTMLElement('.chat-action-icon', candidate);
        if (iconSlot) {
            host.workflow.pageDom.updateHtml(iconSlot, host.rendering.getCachedIcon(iconName, CHAT_ICON_SIZE_SM));
        }
        const labelSlot = host.workflow.pageDom.optionalHTMLElement('.chat-action-label', candidate);
        if (labelSlot) {
            host.workflow.pageDom.updateText(labelSlot, label);
        }
        candidate.dataset['planBarToggleSignature'] = renderSignature;
    }
};

const updateAgentCompactButton = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation | null): void => {
    const show = Boolean(conversation && hasRenderableConversationMessages(conversation));
    const lock = resolveConversationAuthorityLock(conversation);
    const compactTooltip = i18n.t('chat.agent.compact.tooltip');
    for (const candidate of host.workflow.pageDom.query('.agent-compact-btn')) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        host.workflow.pageDom.toggleClass(candidate, 'u-hidden', !show);
        const unlockedDisabled = !show || !conversation || state.manualCompactionStartingConversationId === conversation.id || host.conversation.isConversationExecuting(conversation.id);
        applyAuthorityLockedButtonState(candidate, {
            lock,
            actionLabel: compactTooltip,
            unlockedAriaLabel: compactTooltip,
            unlockedTooltip: compactTooltip,
            unlockedDisabled
        });
    }
};

const updateAgentUiForConversation = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation | null): void => {
    const authorityLock = resolveConversationAuthorityLock(conversation);
    const planBar = resolveAgentPlanBarState(host, state, conversation);
    updateAgentModeBorderIndicator(host, state, conversation);
    updateAgentModeCycleButton(host, conversation, authorityLock);
    updateAgentModeIndicator(host, conversation, authorityLock);
    updateAgentTodoPanel(host, state, planBar);
    updatePlanBarToggleButton(host, planBar);
    updateAgentCompactButton(host, state, conversation);
};

const setManualCompactionStartingState = (host: ChatPageAgentHost, state: ChatPageAgentState, conversationId: string, loading: boolean): void => {
    if (loading) {
        state.manualCompactionStartingConversationId = conversationId;
    } else if (state.manualCompactionStartingConversationId === conversationId) {
        state.manualCompactionStartingConversationId = null;
    }
    for (const candidate of host.workflow.pageDom.query('.agent-compact-btn')) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        const label = host.workflow.pageDom.optionalHTMLElement('.chat-action-label', candidate);
        host.rendering.setButtonLoading?.(candidate, loading, {
            textTarget: label || candidate,
            idleText: i18n.t('chat.agent.compact.label'),
            loadingText: i18n.t('chat.agent.compact.starting')
        });
    }
};

export { setManualCompactionStartingState, updateAgentCompactButton, updateAgentUiForConversation };

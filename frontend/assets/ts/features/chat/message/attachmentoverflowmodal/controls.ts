/* SoAI - Chat attachment overflow modal controls [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/controls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { ATTACHMENT_OVERFLOW_CATEGORY_FILTERS, KNOWLEDGE_STATUS_FILTERS, isAttachmentOverflowCategoryFilter, type AttachmentOverflowCategoryFilter, type KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';

type AttachmentOverflowTabCounts = {
    all: number;
    attachment: number;
    soaiLink: number;
    knowledge: number;
};

type AttachmentOverflowTabsState = {
    activeTab: AttachmentOverflowCategoryFilter;
    counts: AttachmentOverflowTabCounts;
};

type AttachmentOverflowKnowledgeToolbarState = {
    statusFilter: KnowledgeStatusFilter;
    query: string;
    loading: boolean;
};

const categoryLabel = (filter: AttachmentOverflowCategoryFilter): string => {
    if (filter === 'attachment') {
        return i18n.t('chat.attachments.modal.filterAttachments');
    }
    if (filter === 'soaiLink') {
        return i18n.t('chat.attachments.modal.filterSoaiLinks');
    }
    if (filter === 'knowledge') {
        return i18n.t('chat.attachments.modal.filterKnowledge');
    }
    return i18n.t('chat.attachments.modal.filterAll');
};

const statusLabel = (filter: KnowledgeStatusFilter): string => {
    if (filter === 'all') return i18n.t('chat.attachments.modal.status.all');
    if (filter === 'queued') return i18n.t('chat.attachments.modal.status.queued');
    if (filter === 'fetching') return i18n.t('chat.attachments.modal.status.fetching');
    if (filter === 'parsing') return i18n.t('chat.attachments.modal.status.parsing');
    if (filter === 'chunking') return i18n.t('chat.attachments.modal.status.chunking');
    if (filter === 'embedding') return i18n.t('chat.attachments.modal.status.embedding');
    if (filter === 'completed') return i18n.t('chat.attachments.modal.status.completed');
    if (filter === 'error') return i18n.t('chat.attachments.modal.status.error');
    if (filter === 'cancelled') return i18n.t('chat.attachments.modal.status.cancelled');
    return i18n.t('chat.attachments.modal.status.skipped');
};

const countForTab = (counts: AttachmentOverflowTabCounts, filter: AttachmentOverflowCategoryFilter): number => {
    if (filter === 'attachment') return counts.attachment;
    if (filter === 'soaiLink') return counts.soaiLink;
    if (filter === 'knowledge') return counts.knowledge;
    return counts.all;
};

const createTabsContainer = (state: AttachmentOverflowTabsState): HTMLElement => {
    const container = dom.getDocument().createElement('div');
    container.className = 'tabs-container';
    const wrapper = dom.getDocument().createElement('div');
    wrapper.className = 'tabs-nav-wrapper';
    const nav = dom.getDocument().createElement('nav');
    nav.className = 'tabs-nav';
    for (const filter of ATTACHMENT_OVERFLOW_CATEGORY_FILTERS) {
        const label = categoryLabel(filter);
        const button = dom.getDocument().createElement('button');
        button.type = 'button';
        button.className = filter === state.activeTab ? 'tabs-tab is-active' : 'tabs-tab';
        button.dataset['attachmentOverflowAction'] = 'tab';
        button.dataset['attachmentOverflowTab'] = filter;
        button.setAttribute('aria-label', label);
        button.setAttribute('aria-selected', filter === state.activeTab ? 'true' : 'false');
        setTooltipText(button, label);
        const labelNode = dom.getDocument().createElement('span');
        labelNode.className = 'tabs-tab-label';
        labelNode.textContent = label;
        const count = countForTab(state.counts, filter);
        const badge = dom.getDocument().createElement('span');
        badge.className = 'tab-notify-badge';
        badge.textContent = count > 0 ? String(count) : '';
        button.append(labelNode, badge);
        nav.append(button);
    }
    wrapper.append(nav);
    container.append(wrapper);
    return container;
};

const updateExistingTabs = (host: HTMLElement, state: AttachmentOverflowTabsState): boolean => {
    const buttons = dom.resolveAll('[data-attachment-overflow-tab]', host);
    if (buttons.length !== ATTACHMENT_OVERFLOW_CATEGORY_FILTERS.length) {
        return false;
    }
    for (const candidate of buttons) {
        if (!(candidate instanceof HTMLElement)) {
            return false;
        }
        const tab = candidate.dataset['attachmentOverflowTab'];
        if (!isAttachmentOverflowTab(tab)) {
            return false;
        }
        const active = tab === state.activeTab;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-selected', active ? 'true' : 'false');
        const badge = dom.resolve('.tab-notify-badge', candidate);
        if (badge instanceof HTMLElement) {
            const count = countForTab(state.counts, tab);
            badge.textContent = count > 0 ? String(count) : '';
        }
    }
    return true;
};

const isAttachmentOverflowTab = (value: string | undefined): value is AttachmentOverflowCategoryFilter => {
    if (value === undefined) {
        return false;
    }
    return isAttachmentOverflowCategoryFilter(value);
};

const renderAttachmentOverflowTabs = (host: HTMLElement, state: AttachmentOverflowTabsState): void => {
    if (updateExistingTabs(host, state)) {
        return;
    }
    host.replaceChildren(createTabsContainer(state));
};

const appendKnowledgeStatusSelect = (form: HTMLFormElement, state: AttachmentOverflowKnowledgeToolbarState): void => {
    const select = dom.getDocument().createElement('select');
    select.className = 'form-select chat-attachment-overflow-status';
    select.dataset['attachmentOverflowControl'] = 'status';
    select.setAttribute('aria-label', i18n.t('chat.attachments.modal.statusFilter'));
    select.disabled = state.loading;
    for (const filter of KNOWLEDGE_STATUS_FILTERS) {
        const option = dom.getDocument().createElement('option');
        option.value = filter;
        option.textContent = statusLabel(filter);
        option.selected = filter === state.statusFilter;
        select.append(option);
    }
    form.append(select);
};

const createKnowledgeToolbar = (state: AttachmentOverflowKnowledgeToolbarState): HTMLFormElement => {
    const form = dom.getDocument().createElement('form');
    form.className = 'chat-attachment-overflow-toolbar';
    appendKnowledgeStatusSelect(form, state);
    const search = dom.getDocument().createElement('input');
    search.type = 'search';
    search.className = 'chat-attachment-overflow-search';
    search.dataset['attachmentOverflowControl'] = 'query';
    search.value = state.query;
    search.placeholder = i18n.t('chat.attachments.modal.searchPlaceholder');
    search.setAttribute('aria-label', i18n.t('chat.attachments.modal.searchPlaceholder'));
    search.disabled = state.loading;
    form.append(search);
    return form;
};

export { createKnowledgeToolbar, renderAttachmentOverflowTabs };
export type { AttachmentOverflowKnowledgeToolbarState, AttachmentOverflowTabCounts, AttachmentOverflowTabsState };

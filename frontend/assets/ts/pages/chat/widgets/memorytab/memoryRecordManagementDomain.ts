/* SoAI - Memory graph facts and relationships in their management modal [frontend/assets/ts/pages/chat/widgets/memorytab/memoryRecordManagementDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { dom } from '@core/dom/dom.ts';
import { insertWithPresence, removeWithPresence, isPresenceExiting } from '@core/animations/presence/public.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr, uiHtml, uiText, joinUiHtml } from '@core/security/uiHtml.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { memoryAction } from '@pages/chat/widgets/memorytab/memoryPresentationDomain.ts';
import { CHAT_ACTIONS, CHAT_MEMORY_RECORD_MODAL_ID } from '@features/chat/public.ts';

const requireMemoryRecordElement = (content: HTMLElement, selector: string): HTMLElement => {
    const element = dom.resolve(selector, content);
    if (!(element instanceof HTMLElement)) throw new Error(`Memory record element is missing: ${selector}`);
    return element;
};

const patchMemoryRecordRows = (list: HTMLElement, html: TrustedHtml): void => {
    const created = list.ownerDocument.createElement('ul');
    dom.setHTML(created, html);
    patchOrderedChildren({
        existingParent: list,
        createdParent: created,
        resolveChildKey: (child) => child.dataset['memoryRecordId'] ?? null,
        insertChild: (parent, child, anchor) => {
            insertWithPresence(parent, child, anchor);
            return child;
        },
        patchChild: (existing, source) => {
            if (existing.isEqualNode(source)) return false;
            syncElementShell({ target: existing, source });
            reconcileChildNodes(existing, Array.from(source.childNodes));
            return true;
        },
        removeChild: removeWithPresence,
        isChildDetaching: isPresenceExiting,
        replaceUnsupportedChildren: () => {
            list.replaceChildren(...Array.from(created.children));
            return true;
        }
    });
};

const renderMemoryRecordManagement = (content: HTMLElement, entry: ManagedMemoryEntry, staleMessage: string | null): void => {
    const modal = content.closest(`#${CHAT_MEMORY_RECORD_MODAL_ID}`);
    if (modal instanceof HTMLElement) {
        const title = dom.resolve('[data-memory-record-title]', modal);
        if (!(title instanceof HTMLElement)) throw new Error('Memory record modal title is missing');
        title.textContent = entry.entity.name;
    }
    const signature = `${entry.revision}:${staleMessage ?? ''}`;
    if (content.dataset['memoryRevision'] === signature) return;
    const entryId = entry.entity.id;
    const facts = entry.observations.map((fact) => uiHtml`<li class="chat-memory-record-row" data-memory-record-id="${uiAttr(fact.id)}"><div><p>${uiText(fact.content)}</p><span class="text-muted">${uiText(fact.source ?? '')}</span></div><div class="ui-collection-list__actions chat-memory-actions">${fact.profileField ? memoryAction(CHAT_ACTIONS.OPEN_MEMORY_PROFILE, i18n.t('chat.configuration.memory.openProfile'), 'edit', entryId, fact.id) : uiHtml`${memoryAction(CHAT_ACTIONS.DELETE_MEMORY_OBSERVATION, i18n.t('common.delete'), 'close', entryId, fact.id)}${memoryAction(CHAT_ACTIONS.VIEW_MEMORY, i18n.t('common.view'), 'eye-open', entryId, fact.id)}${memoryAction(CHAT_ACTIONS.EDIT_MEMORY_OBSERVATION, i18n.t('common.edit'), 'edit', entryId, fact.id)}`}</div></li>`);
    const relations = entry.relations.map((relation) => uiHtml`<li class="chat-memory-record-row" data-memory-record-id="${uiAttr(relation.id)}"><p>${uiText(relation.fromEntity)} → ${uiText(relation.relationType)} → ${uiText(relation.toEntity)}</p><div class="ui-collection-list__actions chat-memory-actions">${memoryAction(CHAT_ACTIONS.DELETE_MEMORY_RELATION, i18n.t('common.delete'), 'close', entryId, relation.id)}${memoryAction(CHAT_ACTIONS.EDIT_MEMORY_RELATION, i18n.t('common.edit'), 'edit', entryId, relation.id)}</div></li>`);
    if (!content.hasChildNodes()) dom.setHTML(content, uiHtml`<p data-memory-record-status role="status" class="chat-configuration-hint u-hidden"></p><section><h3 data-memory-record-fact-heading></h3><ul data-memory-record-facts></ul></section><section><h3 data-memory-record-relation-heading></h3><ul data-memory-record-relations></ul></section>`);
    const status = requireMemoryRecordElement(content, '[data-memory-record-status]');
    status.classList.toggle('u-hidden', staleMessage === null);
    status.textContent = staleMessage ?? '';
    requireMemoryRecordElement(content, '[data-memory-record-fact-heading]').textContent = `${i18n.t('chat.memory.viewer.observations')} (${entry.observations.length})`;
    requireMemoryRecordElement(content, '[data-memory-record-relation-heading]').textContent = `${i18n.t('chat.memory.viewer.relations')} (${entry.relations.length})`;
    patchMemoryRecordRows(requireMemoryRecordElement(content, '[data-memory-record-facts]'), joinUiHtml(facts));
    patchMemoryRecordRows(requireMemoryRecordElement(content, '[data-memory-record-relations]'), joinUiHtml(relations));
    content.dataset['memoryRevision'] = signature;
};

const openMemoryRecordManagement = (entry: ManagedMemoryEntry): HTMLElement => {
    const presenter = requireModalPresenter();
    const modal = presenter.requireElement(CHAT_MEMORY_RECORD_MODAL_ID);
    const content = dom.resolve('[data-memory-record-content]', modal);
    if (!(content instanceof HTMLElement)) throw new Error('Memory record modal is incomplete');
    renderMemoryRecordManagement(content, entry, null);
    presenter.open(CHAT_MEMORY_RECORD_MODAL_ID);
    return content;
};

export { openMemoryRecordManagement, renderMemoryRecordManagement };

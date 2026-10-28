/* SoAI - Incremental memory library cards and freshness [frontend/assets/ts/pages/chat/widgets/memorytab/memoryPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence, isPresenceExiting } from '@core/animations/presence/public.ts';
import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { checkerboardService, dom } from '@core/dom/dom.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { CHECKERBOARD_CLASS_NAMES } from '@core/dom/checkerboardAssignment.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { createSearchTextIndex, matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { createSearchFieldActions } from '@core/ui/searchField.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createCollectionNoticeAction, renderCollectionEmptyState, renderCollectionNotice, type CollectionNotice } from '@core/ui/collectionFeedback.ts';
import { CHAT_ACTIONS, CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { MemoryLibraryState } from '@pages/chat/widgets/memorytab/contracts.ts';

const requireMemoryElement = (root: HTMLElement, token: string): HTMLElement => {
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, token), root);
    if (!(element instanceof HTMLElement)) throw new Error(`Memory library element is missing: ${token}`);
    return element;
};

const memoryMatchesQuery = (entry: ManagedMemoryEntry, query: string): boolean => matchesSearchFilterQuery(createSearchTextIndex([entry.entity.name, entry.entity.entityType, ...entry.observations.flatMap((fact) => [fact.content, fact.source]), ...entry.relations.flatMap((relation) => [relation.relationType, relation.fromEntity, relation.toEntity])]), query);

const compareMemoryEntryOrder = (left: ManagedMemoryEntry, right: ManagedMemoryEntry): number => {
    const timestampOrder = right.entity.updatedAtMs - left.entity.updatedAtMs || right.entity.createdAtMs - left.entity.createdAtMs;
    if (timestampOrder !== 0) return timestampOrder;
    const leftIdentity = Array.from(left.entity.id, (character) => character.codePointAt(0) ?? 0);
    const rightIdentity = Array.from(right.entity.id, (character) => character.codePointAt(0) ?? 0);
    for (let index = 0; index < Math.min(leftIdentity.length, rightIdentity.length); index += 1) {
        const difference = (leftIdentity[index] ?? 0) - (rightIdentity[index] ?? 0);
        if (difference !== 0) return difference;
    }
    return leftIdentity.length - rightIdentity.length;
};

const memoryAction = (action: string, label: string, icon: IconName, entryId: string, childId: string | null = null) => uiHtml`<button type="button" class="ui-round-button ui-round-button--inline ${uiAttr(icon === 'close' ? 'ui-round-button--delete' : icon === 'edit' ? 'ui-round-button--edit' : 'ui-round-button--settings')}" data-action="${uiAttr(action)}" data-memory-id="${uiAttr(entryId)}" data-memory-child-id="${uiAttr(childId ?? '')}" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}">${getIconSync(icon, { size: 18 })}</button>`;

const card = (entry: ManagedMemoryEntry): HTMLElement => {
    const counts = [entry.observations.length > 0 ? `${i18n.t('chat.memory.viewer.observations')}: ${entry.observations.length}` : '', entry.relations.length > 0 ? `${i18n.t('chat.memory.viewer.relations')}: ${entry.relations.length}` : ''].filter(Boolean).join(' · ');
    const node = dom.getDocument().createElement('article');
    node.dataset['memoryId'] = entry.entity.id;
    node.dataset['memoryRevision'] = entry.revision;
    node.className = 'chat-memory-row collection-list-item glass-surface-interactive';
    node.setAttribute('role', 'listitem');
    dom.setHTML(node, uiHtml`<div class="collection-list-item-main"><h3 class="collection-list-item-title">${uiText(entry.entity.name)}</h3><p class="collection-list-item-meta">${uiText(entry.entity.entityType)}${counts ? uiHtml` · <button type="button" class="ui-button ui-button-xs" aria-label="${uiAttr(counts)}" data-tooltip="${uiAttr(counts)}" data-action="${uiAttr(CHAT_ACTIONS.MANAGE_MEMORY)}" data-memory-id="${uiAttr(entry.entity.id)}">${uiText(counts)}</button>` : uiHtml``}</p><p class="chat-memory-preview">${uiText(entry.observations[0]?.content ?? '')}</p></div><div class="ui-collection-list__actions chat-memory-actions">${memoryAction(CHAT_ACTIONS.DELETE_MEMORY, i18n.t('common.delete'), 'close', entry.entity.id)}${memoryAction(CHAT_ACTIONS.VIEW_MEMORY, i18n.t('common.view'), 'eye-open', entry.entity.id)}${memoryAction(CHAT_ACTIONS.EDIT_MEMORY, i18n.t('common.edit'), 'edit', entry.entity.id)}</div>`);
    return node;
};

const initializeMemoryPresentation = (root: HTMLElement): void => {
    const input = requireMemoryElement(root, 'memory-search');
    if (!(input instanceof HTMLInputElement) || !input.parentElement) throw new Error('Memory search field is missing');
    if (input.parentElement.childElementCount === 1) input.parentElement.append(...createSearchFieldActions(root.ownerDocument));
};

const memoryStaleMessage = (state: MemoryLibraryState): string | null => (state.stale ? i18n.t('chat.memory.library.stale', { time: state.refreshedAt === null ? i18n.t('chat.memory.viewer.none') : formatDateTime(state.refreshedAt) }) : null);

const resolveMemoryStatus = (state: MemoryLibraryState, status: HTMLElement): CollectionNotice | null => {
    const refresh = (): HTMLButtonElement => createCollectionNoticeAction(status.ownerDocument, CHAT_ACTIONS.REFRESH_MEMORY, i18n.t('chat.configuration.memory.refresh'));
    if (state.phase === 'failed' && !state.snapshot) return { tone: 'error', title: i18n.t('chat.memory.library.errorTitle'), detail: i18n.t('chat.memory.errors.loadFailed'), actions: [refresh()] };
    const staleMessage = memoryStaleMessage(state);
    if (staleMessage !== null) return { tone: 'warning', title: i18n.t('chat.memory.library.staleTitle'), detail: staleMessage, actions: [refresh()] };
    return null;
};

const renderMemoryLibrary = (root: HTMLElement, state: MemoryLibraryState): void => {
    const content = requireMemoryElement(root, 'memory-content');
    content.dataset['chatMemoryState'] = state.phase;
    content.dataset['chatLibraryLoading'] = String(state.phase === 'loading' && state.snapshot === null);
    setAriaBusy(content, state.phase === 'loading' || state.pending);
    const search = requireMemoryElement(root, 'memory-search');
    if (search instanceof HTMLInputElement && search.value !== state.query) search.value = state.query;
    const list = requireMemoryElement(root, 'memory-viewer');
    const status = requireMemoryElement(root, 'memory-status');
    const empty = requireMemoryElement(root, 'memory-empty');
    const entries = state.snapshot?.entries.filter((entry) => memoryMatchesQuery(entry, state.query)) ?? [];
    const createdParent = root.ownerDocument.createElement('div');
    createdParent.append(...entries.map(card));
    patchOrderedChildren({
        existingParent: list,
        createdParent,
        resolveChildKey: (child) => child.dataset['memoryId'] ?? null,
        insertChild: (parent, child, anchor) => {
            insertWithPresence(parent, child, anchor);
            return child;
        },
        patchChild: (existing, created) => {
            if (existing.dataset['memoryRevision'] === created.dataset['memoryRevision']) return false;
            syncElementShell({ target: existing, source: created, preservedClassNames: CHECKERBOARD_CLASS_NAMES });
            reconcileChildNodes(existing, Array.from(created.childNodes));
            return true;
        },
        removeChild: removeWithPresence,
        isChildDetaching: isPresenceExiting,
        replaceUnsupportedChildren: () => {
            list.replaceChildren(...Array.from(createdParent.children));
            return true;
        }
    });
    checkerboardService.applyCheckerboard(list, '.chat-memory-row');
    list.classList.toggle('u-hidden', entries.length === 0);
    const emptyLibrary = state.snapshot?.entries.length === 0;
    renderCollectionEmptyState(
        empty,
        state.snapshot && entries.length === 0
            ? {
                  icon: emptyLibrary ? 'file-notebook' : 'search',
                  title: emptyLibrary ? i18n.t('chat.configuration.memory.empty') : i18n.t('chat.memory.library.noMatches'),
                  message: emptyLibrary ? i18n.t('chat.configuration.memory.description') : i18n.t('header.search.noResults', { query: state.query })
              }
            : null
    );
    renderCollectionNotice(status, resolveMemoryStatus(state, status));
    for (const control of dom.resolveAll('[data-action^="chat:"][data-memory-id], [data-action="chat:add-memory"]', root)) {
        if (control instanceof HTMLButtonElement) setControlDisabledState(control, state.pending || state.opening || state.editorOpen);
    }
};

const disconnectMemoryPresentation = (root: HTMLElement): void => {
    const list = requireMemoryElement(root, 'memory-viewer');
    checkerboardService.disconnect(checkerboardService.getContainerId(list));
};

export { compareMemoryEntryOrder, disconnectMemoryPresentation, initializeMemoryPresentation, memoryAction, memoryMatchesQuery, memoryStaleMessage, renderMemoryLibrary, requireMemoryElement };

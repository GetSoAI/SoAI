/* SoAI - Archived conversations modal refs [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/ArchivedConversationsRefsModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ArchivedConversationsModalRefs } from '@pages/chat/controllers/modals/archivedconversations/types.ts';

const requireArchivedModalButton = (root: HTMLElement, selector: string): HTMLButtonElement => {
    const element = dom.resolve(selector, root);
    if (!(element instanceof HTMLButtonElement)) {
        throw new Error(`Archived conversations modal requires button ${selector}`);
    }
    return element;
};

const requireArchivedModalElement = (root: HTMLElement, selector: string): HTMLElement => {
    const element = dom.resolve(selector, root);
    if (!(element instanceof HTMLElement)) {
        throw new Error(`Archived conversations modal requires element ${selector}`);
    }
    return element;
};

const resolveArchivedConversationsModalRefs = (root: HTMLElement): ArchivedConversationsModalRefs => {
    const searchInput = dom.resolve('.archived-conversations-search-input', root);
    if (!(searchInput instanceof HTMLInputElement)) {
        throw new Error('Archived conversations modal requires a search input');
    }
    return {
        root,
        searchInput,
        scrollContainer: requireArchivedModalElement(root, '.archived-conversations-scroll'),
        listContainer: requireArchivedModalElement(root, '.archived-conversations-list'),
        statusElement: requireArchivedModalElement(root, '.archived-conversations-status'),
        totalElement: requireArchivedModalElement(root, '.archived-toolbar-total'),
        selectedElement: requireArchivedModalElement(root, '.archived-toolbar-selected'),
        selectButton: requireArchivedModalButton(root, '.archived-toolbar-select-btn'),
        batchActionsContainer: requireArchivedModalElement(root, '.archived-toolbar-batch-actions'),
        batchUnarchiveButton: requireArchivedModalButton(root, '.archived-toolbar-unarchive-btn'),
        batchDeleteButton: requireArchivedModalButton(root, '.archived-toolbar-delete-btn'),
        exitSelectButton: requireArchivedModalButton(root, '.archived-toolbar-exit-select-btn')
    };
};

export { resolveArchivedConversationsModalRefs };

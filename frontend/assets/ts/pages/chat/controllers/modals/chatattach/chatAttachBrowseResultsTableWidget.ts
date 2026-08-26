/* SoAI - Chat attach modal browse results table widget [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsTableWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { resolveSortableAriaSortValue } from '@core/ui/tables/sortableTable.ts';
import { CHAT_ATTACH_MODAL_ACTIONS } from '@features/chat/public.ts';
import type { ChatAttachBrowseResult, ChatAttachBrowseSortColumn, ChatAttachBrowseSortState } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';

const appendText = (documentRef: Document, parent: HTMLElement, className: string, text: string): HTMLElement => {
    const element = documentRef.createElement('span');
    element.className = className;
    element.textContent = text;
    parent.append(element);
    return element;
};

const createSortIndicator = (documentRef: Document, column: ChatAttachBrowseSortColumn, sortState: ChatAttachBrowseSortState): HTMLElement => {
    const indicator = documentRef.createElement('span');
    indicator.className = 'sort-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    if (sortState.column === column) {
        const iconName = sortState.direction === 'asc' ? 'chevron-up' : 'chevron-down';
        replaceChildrenFromTrustedHtml({ element: indicator, html: getIconSync(iconName, { size: 14, strokeWidth: 2.5 }) });
    }
    return indicator;
};

const createSortableHeader = (documentRef: Document, column: ChatAttachBrowseSortColumn, label: string, sortState: ChatAttachBrowseSortState, colSpan = 1): HTMLTableCellElement => {
    const header = documentRef.createElement('th');
    header.scope = 'col';
    header.colSpan = colSpan;
    header.className = sortState.column === column ? 'sortable is-active' : 'sortable';
    header.dataset['action'] = CHAT_ATTACH_MODAL_ACTIONS.BROWSE_SORT;
    header.dataset['sort'] = column;
    header.tabIndex = 0;
    header.setAttribute('aria-sort', sortState.column === column ? resolveSortableAriaSortValue(sortState.direction) : 'none');
    appendText(documentRef, header, 'chat-attach-results-header-label', label);
    header.append(createSortIndicator(documentRef, column, sortState));
    return header;
};

const createHeader = (documentRef: Document, sortState: ChatAttachBrowseSortState): HTMLTableSectionElement => {
    const head = documentRef.createElement('thead');
    const row = documentRef.createElement('tr');
    row.append(createSortableHeader(documentRef, 'name', i18n.t('fileExplorer.table.name'), sortState, 2), createSortableHeader(documentRef, 'type', i18n.t('fileExplorer.table.type'), sortState), createSortableHeader(documentRef, 'size', i18n.t('fileExplorer.table.size'), sortState), createSortableHeader(documentRef, 'modified', i18n.t('fileExplorer.table.modified'), sortState));
    head.append(row);
    return head;
};

const createNameCell = (documentRef: Document, result: ChatAttachBrowseResult): HTMLTableCellElement => {
    const cell = documentRef.createElement('td');
    cell.className = 'chat-attach-results-name-cell';
    const content = documentRef.createElement('span');
    content.className = 'chat-attach-results-name-content';
    const icon = documentRef.createElement('span');
    icon.className = 'chat-attach-result-item-icon';
    icon.setAttribute('aria-hidden', 'true');
    replaceChildrenFromTrustedHtml({ element: icon, html: getIconSync(result.iconName, { size: 16, strokeWidth: 1.5 }) });
    const copy = documentRef.createElement('span');
    copy.className = 'chat-attach-result-item-copy';
    appendText(documentRef, copy, 'chat-attach-result-item-title', result.title);
    appendText(documentRef, copy, 'chat-attach-result-item-status', result.status);
    content.append(icon, copy);
    cell.append(content);
    return cell;
};

const createSelectCell = (documentRef: Document, result: ChatAttachBrowseResult, selected: boolean): HTMLTableCellElement => {
    const cell = documentRef.createElement('td');
    cell.className = 'chat-attach-results-select-cell';
    const checkbox = documentRef.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = selected;
    checkbox.dataset['action'] = CHAT_ATTACH_MODAL_ACTIONS.BROWSE_SELECT;
    checkbox.dataset['resultKey'] = result.key;
    checkbox.setAttribute('aria-label', result.title);
    cell.append(checkbox);
    return cell;
};

const createMetaCell = (documentRef: Document, text: string): HTMLTableCellElement => {
    const cell = documentRef.createElement('td');
    cell.className = 'chat-attach-results-meta-cell';
    cell.textContent = text;
    return cell;
};

const createTypeCell = (documentRef: Document, result: ChatAttachBrowseResult): HTMLTableCellElement => {
    const cell = documentRef.createElement('td');
    cell.className = 'chat-attach-results-meta-cell chat-attach-results-type-cell';
    const content = documentRef.createElement('span');
    content.className = 'chat-attach-results-type-content';
    appendText(documentRef, content, 'chat-attach-results-type-label', result.typeLabel);
    cell.append(content);
    return cell;
};

const createResultRow = (documentRef: Document, result: ChatAttachBrowseResult, selected: boolean): HTMLTableRowElement => {
    const row = documentRef.createElement('tr');
    row.className = selected ? 'chat-attach-result-row is-active' : 'chat-attach-result-row';
    row.dataset['action'] = CHAT_ATTACH_MODAL_ACTIONS.BROWSE_OPEN;
    row.dataset['resultKey'] = result.key;
    row.setAttribute('aria-selected', selected ? 'true' : 'false');
    setTooltipText(row, result.title);
    row.append(createSelectCell(documentRef, result, selected), createNameCell(documentRef, result), createTypeCell(documentRef, result), createMetaCell(documentRef, result.sizeLabel), createMetaCell(documentRef, result.modifiedLabel));
    return row;
};

const renderEmptyResults = (container: HTMLElement): void => {
    const documentRef = container.ownerDocument;
    const emptyState = documentRef.createElement('div');
    emptyState.className = 'chat-attach-empty-state';
    appendText(documentRef, emptyState, 'chat-attach-empty-state-title', i18n.t('chat.attachModal.browseNoResultsTitle'));
    appendText(documentRef, emptyState, 'chat-attach-modal-hint', i18n.t('chat.attachModal.browseNoResultsSubtitle'));
    container.replaceChildren(emptyState);
};

const renderBrowseResultsTable = (container: HTMLElement, results: readonly ChatAttachBrowseResult[], selectedKey: string | null, sortState: ChatAttachBrowseSortState): void => {
    if (results.length === 0) {
        renderEmptyResults(container);
        return;
    }
    const documentRef = container.ownerDocument;
    const currentWrapperElement = container.firstElementChild;
    const currentWrapper = currentWrapperElement instanceof HTMLElement && currentWrapperElement.classList.contains('chat-attach-modal-results-table-wrap') ? currentWrapperElement : null;
    const scrollTop = currentWrapper === null ? 0 : currentWrapper.scrollTop;
    const scrollLeft = currentWrapper === null ? 0 : currentWrapper.scrollLeft;
    const wrapper = documentRef.createElement('div');
    wrapper.className = 'chat-attach-modal-results-table-wrap';
    const table = documentRef.createElement('table');
    table.className = 'file-explorer-table chat-attach-results-table';
    const body = documentRef.createElement('tbody');
    for (const result of results) {
        body.append(createResultRow(documentRef, result, result.key === selectedKey));
    }
    table.append(createHeader(documentRef, sortState), body);
    wrapper.append(table);
    container.replaceChildren(wrapper);
    wrapper.scrollTop = scrollTop;
    wrapper.scrollLeft = scrollLeft;
};

export { renderBrowseResultsTable };

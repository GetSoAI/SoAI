/* SoAI - Shared UI primitives list table [frontend/assets/ts/core/uiprimitives/listTable.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import { resolveSortableAriaSortValue, type SortDirection } from '@core/ui/tables/sortableTable.ts';

interface ListTableColumn {
    label: string;
    content?: TrustedHtml | undefined;
    className?: string | undefined;
    sortKey?: string | undefined;
    sortAction?: string | undefined;
    active?: boolean | undefined;
    direction?: SortDirection | 'none' | undefined;
}

interface ListTableOptions {
    tableClassName: string;
    bodyId: string;
    columns: readonly ListTableColumn[];
}

const renderListTableHeader = (column: ListTableColumn): string => {
    const classNames = ['ui-collection-list__header-cell'];
    if (column.className) {
        classNames.push(column.className);
    }
    const labelMarkup = column.content?.html ?? `<span class="ui-collection-list__header-label">${uiText(column.label).html}</span>`;
    if (!column.sortKey || !column.sortAction) {
        return `<th class="${uiAttr(classNames.join(' ')).html}" ${renderLabelAttributes(column.label)}>${labelMarkup}</th>`;
    }
    classNames.push('sortable');
    if (column.active) {
        classNames.push('is-active');
    }
    const direction = column.direction ?? 'none';
    const ariaSort = resolveSortableAriaSortValue(direction);
    return `<th class="${uiAttr(classNames.join(' ')).html}" data-action="${uiAttr(column.sortAction).html}" data-sort="${uiAttr(column.sortKey).html}" tabindex="0" role="columnheader" aria-sort="${uiAttr(ariaSort).html}" ${renderLabelAttributes(column.label)}>${labelMarkup}<span class="sort-indicator"></span></th>`;
};

const renderListTable = (options: ListTableOptions): string => {
    const headers = options.columns.map((column) => renderListTableHeader(column)).join('');
    return `<table class="${uiAttr(options.tableClassName).html} ui-collection-list__table"><thead><tr>${headers}</tr></thead><tbody id="${uiAttr(options.bodyId).html}"></tbody></table>`;
};

export { renderListTable };
export type { ListTableColumn, ListTableOptions };

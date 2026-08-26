/* SoAI - Shared frontend MCP tool search filter [frontend/assets/ts/core/mcp/toolSearchFilter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { matchesSearchFilterQuery } from '@core/search/searchQuery.ts';

const filterMcpToolGroupTools = (element: Element): void => {
    if (!(element instanceof HTMLInputElement)) {
        throw new TypeError('MCP tool search filter requires an input element');
    }
    const bodyInner = element.closest('.mcp-tool-group-body-inner');
    if (!(bodyInner instanceof HTMLElement)) {
        throw new Error('MCP tool search input is missing its tool group body');
    }
    const query = element.value;
    for (const row of dom.resolveAll('.mcp-tool-item', bodyInner)) {
        if (!(row instanceof HTMLElement)) {
            throw new Error('MCP tool search row must be an element');
        }
        row.classList.toggle('u-hidden', !matchesSearchFilterQuery(row.dataset['toolSearch'] ?? '', query));
    }
};

export { filterMcpToolGroupTools };

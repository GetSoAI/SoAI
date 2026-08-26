/* SoAI - Shared frontend MCP tool group toggle [frontend/assets/ts/core/mcp/toolGroupToggle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

interface McpToolGroupToggleResult {
    serverId: string;
    expanded: boolean;
}

const applyMcpToolGroupToggle = (element: Element): McpToolGroupToggleResult => {
    const group = element.closest('.mcp-tool-group');
    if (!(group instanceof HTMLElement)) {
        throw new Error('MCP tool group toggle is missing its group container');
    }
    const serverId = group.dataset['serverId'] ?? '';
    if (!serverId) {
        throw new Error('MCP tool group toggle is missing its server identifier');
    }
    const buttons = dom.resolveAll('.mcp-tool-group-toggle-button, .mcp-tool-group-chevron-button', group);
    if (buttons.length === 0) {
        throw new Error('MCP tool group toggle requires toggle controls');
    }
    for (const button of buttons) {
        if (!(button instanceof HTMLButtonElement)) {
            throw new Error('MCP tool group toggle control must be a button');
        }
    }
    const body = dom.resolve('.mcp-tool-group-body', group);
    if (!(body instanceof HTMLElement)) {
        throw new Error('MCP tool group toggle is missing its body');
    }
    const expanded = group.classList.contains('is-collapsed');
    group.classList.toggle('is-collapsed', !expanded);
    group.classList.toggle('is-expanded', expanded);
    body.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    buttons.forEach((button) => {
        button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        button.classList.toggle('mcp-tool-group-collapse-toggle--collapsed', !expanded && button.classList.contains('mcp-tool-group-collapse-toggle'));
    });
    return { serverId, expanded };
};

export { applyMcpToolGroupToggle };
export type { McpToolGroupToggleResult };

/* SoAI - Sync MCP form defaults to current values [frontend/assets/ts/features/settings/mcp/mcpFormDefaultsSyncController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { syncSelectDefaultSelectedToCurrent } from '@core/dom/selectSelection.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';

const syncDefaultState = (field: Element | null): void => {
    if (!field) {
        return;
    }
    if (field instanceof HTMLSelectElement) {
        syncSelectDefaultSelectedToCurrent(field);
        return;
    }
    if (field instanceof HTMLTextAreaElement) {
        field.defaultValue = field.value;
        return;
    }
    if (field instanceof HTMLInputElement) {
        if (field.type === 'checkbox') {
            field.defaultChecked = field.checked;
            if (field.checked) {
                field.setAttribute('checked', '');
            } else {
                field.removeAttribute('checked');
            }
            return;
        }
        field.defaultValue = field.value;
        return;
    }
};

const resolveDefaultTrackedMcpField = (container: Element, fieldId: string, modalId?: string): Element | null => {
    const direct = dom.resolve(`#${fieldId}`, container);
    if (direct) {
        return direct;
    }
    if (!modalId || !fieldId.startsWith('mcp-server-')) {
        return direct;
    }
    const token = fieldId.slice('mcp-server-'.length);
    return dom.resolve(modalUiSelector(modalId, token), container);
};

const syncMcpFormDefaultsToCurrent = (container: Element, options: { modalId?: string } = {}): void => {
    const { modalId } = options;
    const resolveField = (fieldId: string): Element | null => resolveDefaultTrackedMcpField(container, fieldId, modalId);

    syncDefaultState(resolveField('mcp-server-name-input'));
    syncDefaultState(resolveField('mcp-server-transport-select'));
    syncDefaultState(resolveField('mcp-server-endpoint-input'));
    syncDefaultState(resolveField('mcp-server-auth-select'));
    syncDefaultState(resolveField('mcp-server-timeout-input'));
    syncDefaultState(resolveField('mcp-server-auto-reconnect-toggle'));
    syncDefaultState(resolveField('mcp-server-enabled-toggle'));
    syncDefaultState(resolveField('mcp-server-args-input'));
    syncDefaultState(resolveField('mcp-server-env-input'));
    syncDefaultState(resolveField('mcp-server-headers-input'));
    syncDefaultState(resolveField('mcp-server-api-key-input'));
    syncDefaultState(resolveField('mcp-server-oauth-client-id-input'));
    syncDefaultState(resolveField('mcp-server-oauth-client-secret-input'));

    syncDefaultState(resolveField('mcp-search-provider-select'));
    syncDefaultState(resolveField('mcp-search-provider-input'));
    syncDefaultState(resolveField('mcp-search-api-key-input'));

    syncDefaultState(resolveField('mcp-root-uri-input'));
    syncDefaultState(resolveField('mcp-root-name-input'));
};

export { syncMcpFormDefaultsToCurrent };

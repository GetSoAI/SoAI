/* SoAI - Settings feature MCP server modal UI controller [frontend/assets/ts/features/settings/mcp/mcpServerModalUiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpServer } from '@core/mcp/contracts.ts';
import { MCP_SERVER_TRANSPORT_STDIO, MCP_SERVER_TRANSPORT_STREAMABLE_HTTP } from '@core/mcp/serverValues.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import type { McpServerModalElements } from '@features/settings/mcp/dom.ts';
import { MCP_SERVER_TIMEOUT_DEFAULT_SECONDS, isMcpServerApiKeyVisible, isMcpServerNoneAuth, isMcpServerOauthFlow, resolveMcpServerDefaultAuthType } from '@features/settings/mcp/mcpServerFormRules.ts';
import { formatMcpServerJsonFieldValue } from '@features/settings/mcp/mcpServerJsonFields.ts';
import type { McpServerModalMode } from '@features/settings/mcp/mcpServerModalSaveController.ts';

type McpServerModalFormStateContext = {
    mode: McpServerModalMode;
    transportSelect: HTMLSelectElement;
    authSelect: HTMLSelectElement;
    apiKeyItem: HTMLElement;
    oauthManualSection: HTMLElement;
    oauthClientIdInput: HTMLInputElement;
    enabledItem: HTMLElement;
    enabledToggle: HTMLInputElement;
    saveButton: HTMLButtonElement;
    revealManualOauthClient: boolean;
};

const clearMcpServerModalSummary = (summary: HTMLElement): void => {
    clearStatusSurface(summary);
};

const setMcpServerModalSummary = (summary: HTMLElement, message: string): void => {
    setStatusSurface({
        surface: summary,
        message
    });
};

const syncMcpServerAuthOptions = (authSelect: HTMLSelectElement, transport: string): void => {
    for (const option of Array.from(authSelect.options)) {
        option.disabled = transport === MCP_SERVER_TRANSPORT_STDIO && !isMcpServerNoneAuth(option.value);
    }
};

const syncMcpServerModalFormState = (dependencies: McpServerModalFormStateContext): void => {
    const transport = readTrimmedSelectValue(dependencies.transportSelect);
    syncMcpServerAuthOptions(dependencies.authSelect, transport);
    if (transport === MCP_SERVER_TRANSPORT_STDIO) {
        dependencies.authSelect.value = resolveMcpServerDefaultAuthType(transport);
    } else if (!readTrimmedSelectValue(dependencies.authSelect)) {
        dependencies.authSelect.value = resolveMcpServerDefaultAuthType(transport);
    }

    const auth = readTrimmedSelectValue(dependencies.authSelect);
    setVisibilityState(dependencies.apiKeyItem, isMcpServerApiKeyVisible(transport, auth));

    const isOauth = isMcpServerOauthFlow(transport, auth);
    const manualOauthVisible = isOauth && (dependencies.revealManualOauthClient || Boolean(readTrimmedInputValue(dependencies.oauthClientIdInput)));
    setVisibilityState(dependencies.oauthManualSection, manualOauthVisible, { mode: 'hiddenAttribute' });

    setVisibilityState(dependencies.enabledItem, dependencies.mode === 'edit');
    if (dependencies.mode !== 'edit') {
        dependencies.enabledToggle.checked = true;
        setControlDisabledState(dependencies.enabledToggle, true);
    } else {
        setControlDisabledState(dependencies.enabledToggle, false);
    }

    if (dependencies.mode === 'edit') {
        dependencies.saveButton.textContent = isOauth ? i18n.t('settings.mcp.servers.actions.updateAuthorize') : i18n.t('settings.mcp.servers.actions.updateConnect');
        return;
    }
    dependencies.saveButton.textContent = isOauth ? i18n.t('settings.mcp.servers.actions.saveAuthorize') : i18n.t('settings.mcp.servers.actions.saveConnect');
};

const setMcpServerModalFormValues = (elements: McpServerModalElements, server: McpServer | null): void => {
    elements.nameInput.value = server ? server.name : '';
    elements.transportSelect.value = server ? server.transportType : MCP_SERVER_TRANSPORT_STREAMABLE_HTTP;
    elements.authSelect.value = server ? server.authType : resolveMcpServerDefaultAuthType(elements.transportSelect.value);
    elements.endpointInput.value = server ? server.endpoint : '';
    elements.timeoutInput.value = server && typeof server.timeoutMs === 'number' ? String(Math.ceil(server.timeoutMs / 1000)) : String(MCP_SERVER_TIMEOUT_DEFAULT_SECONDS);
    elements.autoReconnectToggle.checked = server ? server.autoReconnect : true;
    elements.enabledToggle.checked = server ? server.enabled : true;

    elements.argumentsTextarea.value = formatMcpServerJsonFieldValue(server ? server.inputArguments : null);
    elements.envTextarea.value = formatMcpServerJsonFieldValue(server ? server.env : null);
    elements.headersTextarea.value = formatMcpServerJsonFieldValue(server ? server.headers : null);

    elements.apiKeyInput.value = '';
    elements.oauthClientIdInput.value = server && server.oauthClientId ? server.oauthClientId : '';
    elements.oauthClientSecretInput.value = '';
};

export { clearMcpServerModalSummary, setMcpServerModalFormValues, setMcpServerModalSummary, syncMcpServerModalFormState };
export type { McpServerModalMode };

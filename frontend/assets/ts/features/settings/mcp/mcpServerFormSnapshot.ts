/* SoAI - MCP server form field snapshot helpers [frontend/assets/ts/features/settings/mcp/mcpServerFormSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readOptionalTrimmedInputValue, readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { optionalInput, optionalSelect, optionalTextarea } from '@core/dom/narrowElement.ts';
import { getSelectDefaultValue } from '@core/dom/selectSelection.ts';
import { requireInputElement, requireSelectElement, requireTextareaElement, type ElementResolver } from '@core/dom/typedElements.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface McpServerFormFieldHost extends PageDomOwnerHost {
    formRoot?: HTMLElement | undefined;
    resolver?: ElementResolver | undefined;
}

interface McpServerFormHost extends McpServerFormFieldHost {
    warnAndFocus: (element: Element | null, message: string) => void;
}

interface McpServerFormFields {
    nameInput: HTMLInputElement;
    transportSelect: HTMLSelectElement;
    endpointInput: HTMLInputElement;
    authSelect: HTMLSelectElement;
    timeoutInput: HTMLInputElement;
    autoToggle: HTMLInputElement;
    enabledToggle: HTMLInputElement | null;
    argumentsInput: HTMLTextAreaElement;
    envInput: HTMLTextAreaElement;
    headersInput: HTMLTextAreaElement;
    apiKeyInput: HTMLInputElement | null;
    oauthClientIdInput: HTMLInputElement | null;
    oauthClientSecretInput: HTMLInputElement | null;
}

interface McpServerOptionalFormFields {
    nameInput: HTMLInputElement | null;
    transportSelect: HTMLSelectElement | null;
    endpointInput: HTMLInputElement | null;
    authSelect: HTMLSelectElement | null;
    timeoutInput: HTMLInputElement | null;
    autoToggle: HTMLInputElement | null;
    enabledToggle: HTMLInputElement | null;
    argumentsInput: HTMLTextAreaElement | null;
    envInput: HTMLTextAreaElement | null;
    headersInput: HTMLTextAreaElement | null;
    apiKeyInput: HTMLInputElement | null;
    oauthClientIdInput: HTMLInputElement | null;
    oauthClientSecretInput: HTMLInputElement | null;
}

interface McpServerFormTextSnapshot {
    name: string;
    transportType: string;
    endpoint: string;
    authType: string;
    timeoutText: string;
    autoReconnect: boolean;
    enabled: boolean;
    argumentsText: string;
    envText: string;
    headersText: string;
    apiKey: string | null;
    oauthClientId: string | null;
    oauthClientSecret: string | null;
}

const requireResolver = (host: McpServerFormFieldHost): ElementResolver => {
    if (!host.resolver) {
        throw new Error('MCP server form resolver is required');
    }
    return host.resolver;
};

const resolveOptionalInput = (host: McpServerFormFieldHost, modalId: string, id: string): HTMLInputElement | null => optionalInput(host.pageDom.optional(modalUiSelector(modalId, id), host.formRoot), `MCP server form field "${id}"`);

const resolveOptionalSelect = (host: McpServerFormFieldHost, modalId: string, id: string): HTMLSelectElement | null => optionalSelect(host.pageDom.optional(modalUiSelector(modalId, id), host.formRoot), `MCP server form field "${id}"`);

const resolveOptionalTextarea = (host: McpServerFormFieldHost, modalId: string, id: string): HTMLTextAreaElement | null => optionalTextarea(host.pageDom.optional(modalUiSelector(modalId, id), host.formRoot), `MCP server form field "${id}"`);

const resolveRequiredMcpServerFormFields = (host: McpServerFormFieldHost, modalId: string): McpServerFormFields => {
    const resolver = requireResolver(host);
    return {
        nameInput: requireInputElement(resolver, modalUiSelector(modalId, 'name-input'), 'MCP server form name-input'),
        transportSelect: requireSelectElement(resolver, modalUiSelector(modalId, 'transport-select'), 'MCP server form transport-select'),
        endpointInput: requireInputElement(resolver, modalUiSelector(modalId, 'endpoint-input'), 'MCP server form endpoint-input'),
        authSelect: requireSelectElement(resolver, modalUiSelector(modalId, 'auth-select'), 'MCP server form auth-select'),
        timeoutInput: requireInputElement(resolver, modalUiSelector(modalId, 'timeout-input'), 'MCP server form timeout-input'),
        autoToggle: requireInputElement(resolver, modalUiSelector(modalId, 'auto-reconnect-toggle'), 'MCP server form auto-reconnect-toggle'),
        enabledToggle: resolveOptionalInput(host, modalId, 'enabled-toggle'),
        argumentsInput: requireTextareaElement(resolver, modalUiSelector(modalId, 'args-input'), 'MCP server form args-input'),
        envInput: requireTextareaElement(resolver, modalUiSelector(modalId, 'env-input'), 'MCP server form env-input'),
        headersInput: requireTextareaElement(resolver, modalUiSelector(modalId, 'headers-input'), 'MCP server form headers-input'),
        apiKeyInput: resolveOptionalInput(host, modalId, 'api-key-input'),
        oauthClientIdInput: resolveOptionalInput(host, modalId, 'oauth-client-id-input'),
        oauthClientSecretInput: resolveOptionalInput(host, modalId, 'oauth-client-secret-input')
    };
};

const resolveOptionalMcpServerFormFields = (host: McpServerFormFieldHost, modalId: string): McpServerOptionalFormFields => ({
    nameInput: resolveOptionalInput(host, modalId, 'name-input'),
    transportSelect: resolveOptionalSelect(host, modalId, 'transport-select'),
    endpointInput: resolveOptionalInput(host, modalId, 'endpoint-input'),
    authSelect: resolveOptionalSelect(host, modalId, 'auth-select'),
    timeoutInput: resolveOptionalInput(host, modalId, 'timeout-input'),
    autoToggle: resolveOptionalInput(host, modalId, 'auto-reconnect-toggle'),
    enabledToggle: resolveOptionalInput(host, modalId, 'enabled-toggle'),
    argumentsInput: resolveOptionalTextarea(host, modalId, 'args-input'),
    envInput: resolveOptionalTextarea(host, modalId, 'env-input'),
    headersInput: resolveOptionalTextarea(host, modalId, 'headers-input'),
    apiKeyInput: resolveOptionalInput(host, modalId, 'api-key-input'),
    oauthClientIdInput: resolveOptionalInput(host, modalId, 'oauth-client-id-input'),
    oauthClientSecretInput: resolveOptionalInput(host, modalId, 'oauth-client-secret-input')
});

const readMcpServerFormTextSnapshot = (fields: McpServerFormFields): McpServerFormTextSnapshot => ({
    name: readTrimmedInputValue(fields.nameInput),
    transportType: readTrimmedSelectValue(fields.transportSelect),
    endpoint: readTrimmedInputValue(fields.endpointInput),
    authType: readTrimmedSelectValue(fields.authSelect),
    timeoutText: readTrimmedInputValue(fields.timeoutInput),
    autoReconnect: fields.autoToggle.checked,
    enabled: fields.enabledToggle ? fields.enabledToggle.checked : true,
    argumentsText: fields.argumentsInput.value,
    envText: fields.envInput.value,
    headersText: fields.headersInput.value,
    apiKey: readOptionalTrimmedInputValue(fields.apiKeyInput),
    oauthClientId: readOptionalTrimmedInputValue(fields.oauthClientIdInput),
    oauthClientSecret: readOptionalTrimmedInputValue(fields.oauthClientSecretInput)
});

const isChangedValue = (field: Element | null): boolean => {
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
        return field.value !== field.defaultValue;
    }
    if (field instanceof HTMLSelectElement) {
        return field.value !== getSelectDefaultValue(field);
    }
    return false;
};

const isChangedToggle = (field: Element | null): boolean => field instanceof HTMLInputElement && field.type === 'checkbox' && field.checked !== field.defaultChecked;

const hasMcpServerFormFieldChanges = (fields: McpServerOptionalFormFields): boolean => {
    return isChangedValue(fields.nameInput) || isChangedValue(fields.transportSelect) || isChangedValue(fields.endpointInput) || isChangedValue(fields.authSelect) || isChangedValue(fields.timeoutInput) || isChangedToggle(fields.autoToggle) || isChangedToggle(fields.enabledToggle) || isChangedValue(fields.argumentsInput) || isChangedValue(fields.envInput) || isChangedValue(fields.headersInput) || isChangedValue(fields.apiKeyInput) || isChangedValue(fields.oauthClientIdInput) || isChangedValue(fields.oauthClientSecretInput);
};

export { hasMcpServerFormFieldChanges, readMcpServerFormTextSnapshot, resolveOptionalMcpServerFormFields, resolveRequiredMcpServerFormFields };
export type { McpServerFormFieldHost, McpServerFormFields, McpServerFormHost, McpServerFormTextSnapshot };

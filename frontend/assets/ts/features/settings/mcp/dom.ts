/* SoAI - MCP settings DOM helpers (including MCP server modal queries) [frontend/assets/ts/features/settings/mcp/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement } from '@core/dom/typedElements.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { resolveRequiredMcpServerFormFields, type McpServerFormFieldHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';

type McpServerModalElements = {
    title: HTMLElement;
    summary: HTMLElement;
    nameInput: HTMLInputElement;
    transportSelect: HTMLSelectElement;
    authSelect: HTMLSelectElement;
    endpointInput: HTMLInputElement;
    timeoutInput: HTMLInputElement;
    autoReconnectToggle: HTMLInputElement;
    enabledItem: HTMLElement;
    enabledToggle: HTMLInputElement;
    apiKeyItem: HTMLElement;
    apiKeyInput: HTMLInputElement;
    oauthManualSection: HTMLElement;
    oauthClientIdInput: HTMLInputElement;
    oauthClientSecretInput: HTMLInputElement;
    argumentsTextarea: HTMLTextAreaElement;
    envTextarea: HTMLTextAreaElement;
    headersTextarea: HTMLTextAreaElement;
    saveButton: HTMLButtonElement;
};

const requireModalFormInput = (element: HTMLInputElement | null, label: string): HTMLInputElement => {
    if (!element) {
        throw new Error(`${label} is required`);
    }
    return element;
};

const resolveMcpServerModalElements = (pageDom: PageDom, modalRoot: HTMLElement, modalId: string): McpServerModalElements => {
    const resolver = createModalElementResolver(modalRoot, 'MCP server modal');
    const formHost: McpServerFormFieldHost = {
        pageDom,
        formRoot: modalRoot,
        resolver
    };
    const formFields = resolveRequiredMcpServerFormFields(formHost, modalId);
    return {
        title: resolver.requireHTMLElement(modalUiSelector(modalId, 'title'), modalRoot),
        summary: resolver.requireHTMLElement(modalUiSelector(modalId, 'summary'), modalRoot),
        nameInput: formFields.nameInput,
        transportSelect: formFields.transportSelect,
        authSelect: formFields.authSelect,
        endpointInput: formFields.endpointInput,
        timeoutInput: formFields.timeoutInput,
        autoReconnectToggle: formFields.autoToggle,
        enabledItem: resolver.requireHTMLElement(modalUiSelector(modalId, 'enabled-item'), modalRoot),
        enabledToggle: requireModalFormInput(formFields.enabledToggle, 'MCP server modal enabled-toggle'),
        apiKeyItem: resolver.requireHTMLElement(modalUiSelector(modalId, 'api-key-item'), modalRoot),
        apiKeyInput: requireModalFormInput(formFields.apiKeyInput, 'MCP server modal api-key-input'),
        oauthManualSection: resolver.requireHTMLElement(modalUiSelector(modalId, 'oauth-manual-client'), modalRoot),
        oauthClientIdInput: requireModalFormInput(formFields.oauthClientIdInput, 'MCP server modal oauth-client-id-input'),
        oauthClientSecretInput: requireModalFormInput(formFields.oauthClientSecretInput, 'MCP server modal oauth-client-secret-input'),
        argumentsTextarea: formFields.argumentsInput,
        envTextarea: formFields.envInput,
        headersTextarea: formFields.headersInput,
        saveButton: requireButtonElement(resolver, modalUiSelector(modalId, 'save-btn'), 'MCP server modal save-btn', modalRoot)
    };
};

export { resolveMcpServerModalElements };
export type { McpServerModalElements };

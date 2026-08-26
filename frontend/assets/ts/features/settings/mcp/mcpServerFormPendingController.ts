/* SoAI - Settings feature MCP server form pending controller [frontend/assets/ts/features/settings/mcp/mcpServerFormPendingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readBoundedCeiledIntegerInputValueOrNull } from '@core/dom/formValues.ts';
import { isMcpServerAuthCompatibleWithTransport, isMcpServerAuthType, isMcpServerTransportType, type McpServerAuthType } from '@core/mcp/serverValues.ts';
import { hasMcpServerFormFieldChanges, readMcpServerFormTextSnapshot, resolveOptionalMcpServerFormFields, type McpServerFormFields, type McpServerFormHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import { isMcpServerArgumentsTextValid, isMcpServerScalarRecordTextValid } from '@features/settings/mcp/mcpServerJsonFields.ts';
import { MCP_SERVER_TIMEOUT_MAX_SECONDS, MCP_SERVER_TIMEOUT_MIN_SECONDS, hasMcpServerNoneAuthApiKeyConflict, isMcpServerApiKeyRequired, isMcpServerOauthAuth } from '@features/settings/mcp/mcpServerFormRules.ts';

const resolveCompleteMcpServerFormFields = (host: McpServerFormHost, modalId: string): McpServerFormFields | null => {
    const fields = resolveOptionalMcpServerFormFields(host, modalId);
    if (!fields.nameInput || !fields.transportSelect || !fields.endpointInput || !fields.authSelect || !fields.timeoutInput || !fields.autoToggle || !fields.argumentsInput || !fields.envInput || !fields.headersInput) {
        return null;
    }
    return {
        nameInput: fields.nameInput,
        transportSelect: fields.transportSelect,
        endpointInput: fields.endpointInput,
        authSelect: fields.authSelect,
        timeoutInput: fields.timeoutInput,
        autoToggle: fields.autoToggle,
        enabledToggle: fields.enabledToggle,
        apiKeyInput: fields.apiKeyInput,
        oauthClientIdInput: fields.oauthClientIdInput,
        oauthClientSecretInput: fields.oauthClientSecretInput,
        argumentsInput: fields.argumentsInput,
        envInput: fields.envInput,
        headersInput: fields.headersInput
    };
};

const hasMcpServerFormPendingChanges = (host: McpServerFormHost, modalId: string): boolean => {
    const fields = resolveOptionalMcpServerFormFields(host, modalId);
    if (!fields.nameInput) {
        return false;
    }
    return hasMcpServerFormFieldChanges(fields);
};

const isMcpServerFormPendingChangesValid = (host: McpServerFormHost, modalId: string, baselineAuthType: McpServerAuthType | null): boolean => {
    if (!hasMcpServerFormPendingChanges(host, modalId)) {
        return true;
    }
    const fields = resolveCompleteMcpServerFormFields(host, modalId);
    if (!fields) {
        return false;
    }

    const snapshot = readMcpServerFormTextSnapshot(fields);
    const transport = snapshot.transportType;
    const auth = snapshot.authType;
    if (!snapshot.name) {
        return false;
    }
    if (!isMcpServerTransportType(transport)) {
        return false;
    }
    if (!isMcpServerAuthType(auth)) {
        return false;
    }
    if (!isMcpServerAuthCompatibleWithTransport(transport, auth)) {
        return false;
    }
    const apiKey = snapshot.apiKey;
    if (hasMcpServerNoneAuthApiKeyConflict(transport, auth, apiKey)) {
        return false;
    }
    if (isMcpServerApiKeyRequired(transport, auth, apiKey, baselineAuthType)) {
        return false;
    }
    if (!isMcpServerOauthAuth(auth)) {
        if (snapshot.oauthClientId) {
            return false;
        }
        if (snapshot.oauthClientSecret) {
            return false;
        }
    }
    if (!snapshot.endpoint) {
        return false;
    }
    if (snapshot.timeoutText && readBoundedCeiledIntegerInputValueOrNull(fields.timeoutInput, MCP_SERVER_TIMEOUT_MIN_SECONDS, MCP_SERVER_TIMEOUT_MAX_SECONDS) === null) {
        return false;
    }
    if (!isMcpServerArgumentsTextValid(snapshot.argumentsText)) {
        return false;
    }
    if (!isMcpServerScalarRecordTextValid(snapshot.envText)) {
        return false;
    }
    if (!isMcpServerScalarRecordTextValid(snapshot.headersText)) {
        return false;
    }
    return true;
};

export { hasMcpServerFormPendingChanges, isMcpServerFormPendingChangesValid };

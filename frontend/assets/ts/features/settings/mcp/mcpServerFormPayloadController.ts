/* SoAI - MCP server form payload validation [frontend/assets/ts/features/settings/mcp/mcpServerFormPayloadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readBoundedCeiledIntegerInputValueOrNull } from '@core/dom/formValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { isMcpServerAuthCompatibleWithTransport, isMcpServerAuthType, isMcpServerTransportType, type McpServerAuthType } from '@core/mcp/serverValues.ts';
import { parseJsonFormValue } from '@core/serialization/jsonForm.ts';
import type { McpServerFormData } from '@features/settings/mcp/mcpManagerTypes.ts';
import { readMcpServerFormTextSnapshot, resolveRequiredMcpServerFormFields, type McpServerFormFields, type McpServerFormHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import { parseMcpServerArgumentsText, parseMcpServerScalarRecordText } from '@features/settings/mcp/mcpServerJsonFields.ts';
import { MCP_SERVER_TIMEOUT_MAX_SECONDS, MCP_SERVER_TIMEOUT_MIN_SECONDS, hasMcpServerNoneAuthApiKeyConflict, isMcpServerApiKeyRequired } from '@features/settings/mcp/mcpServerFormRules.ts';

type McpServerFormDraft = Omit<McpServerFormData, 'transportType' | 'authType'> & {
    transportType: string;
    authType: string;
};

type McpServerFormDraftRead = {
    fields: McpServerFormFields;
    payload: McpServerFormDraft;
};

const parseJsonArray = (host: McpServerFormHost, value: string, input: HTMLTextAreaElement): string[] | null | undefined => {
    const result = parseJsonFormValue(parseMcpServerArgumentsText, value);
    if (!result.ok) {
        errorHandler.warn('SettingsPage', 'Invalid MCP server JSON array field', result.error);
        host.warnAndFocus(input, i18n.t('settings.mcp.notifications.jsonInvalid'));
        return undefined;
    }
    return result.value;
};

const parseJsonRecord = (host: McpServerFormHost, value: string, input: HTMLTextAreaElement): Record<string, string> | null | undefined => {
    const result = parseJsonFormValue(parseMcpServerScalarRecordText, value);
    if (!result.ok) {
        errorHandler.warn('SettingsPage', 'Invalid MCP server JSON object field', result.error);
        host.warnAndFocus(input, i18n.t('settings.mcp.notifications.jsonInvalid'));
        return undefined;
    }
    return result.value;
};

const readMcpServerForm = (host: McpServerFormHost, modalId: string): McpServerFormDraftRead | null => {
    const fields = resolveRequiredMcpServerFormFields(host, modalId);
    const snapshot = readMcpServerFormTextSnapshot(fields);

    const inputArguments = parseJsonArray(host, snapshot.argumentsText, fields.argumentsInput);
    if (inputArguments === undefined) {
        return null;
    }

    const env = parseJsonRecord(host, snapshot.envText, fields.envInput);
    if (env === undefined) {
        return null;
    }

    const headers = parseJsonRecord(host, snapshot.headersText, fields.headersInput);
    if (headers === undefined) {
        return null;
    }

    const timeoutSeconds = readBoundedCeiledIntegerInputValueOrNull(fields.timeoutInput, MCP_SERVER_TIMEOUT_MIN_SECONDS, MCP_SERVER_TIMEOUT_MAX_SECONDS);
    if (snapshot.timeoutText && timeoutSeconds === null) {
        host.warnAndFocus(fields.timeoutInput, i18n.t('settings.mcp.servers.form.timeout.help'));
        return null;
    }

    return {
        fields,
        payload: {
            name: snapshot.name,
            transportType: snapshot.transportType,
            endpoint: snapshot.endpoint,
            authType: snapshot.authType,
            timeoutMs: timeoutSeconds !== null ? timeoutSeconds * 1000 : null,
            autoReconnect: snapshot.autoReconnect,
            enabled: snapshot.enabled,
            inputArguments,
            env,
            headers,
            apiKey: snapshot.apiKey,
            oauthClientId: snapshot.oauthClientId,
            oauthClientSecret: snapshot.oauthClientSecret
        }
    };
};

const validateMcpServerForm = (host: McpServerFormHost, modalId: string, baselineAuthType: McpServerAuthType | null): McpServerFormData | null => {
    const draft = readMcpServerForm(host, modalId);
    if (!draft) {
        return null;
    }
    const { fields, payload } = draft;
    if (!payload.name) {
        host.warnAndFocus(fields.nameInput, i18n.t('settings.mcp.notifications.serverNameRequired'));
        return null;
    }
    const transportType = payload.transportType;
    if (!isMcpServerTransportType(transportType)) {
        host.warnAndFocus(fields.transportSelect, i18n.t('settings.mcp.notifications.serverTransportRequired'));
        return null;
    }
    if (!payload.endpoint) {
        host.warnAndFocus(fields.endpointInput, i18n.t('settings.mcp.notifications.serverEndpointRequired'));
        return null;
    }
    const authType = payload.authType;
    if (!isMcpServerAuthType(authType)) {
        host.warnAndFocus(fields.authSelect, i18n.t('settings.mcp.notifications.serverAuthRequired'));
        return null;
    }
    if (hasMcpServerNoneAuthApiKeyConflict(transportType, authType, payload.apiKey)) {
        host.warnAndFocus(fields.apiKeyInput, i18n.t('settings.mcp.notifications.serverAuthInvalid'));
        return null;
    }
    if (isMcpServerApiKeyRequired(transportType, authType, payload.apiKey, baselineAuthType)) {
        host.warnAndFocus(fields.apiKeyInput, i18n.t('settings.mcp.notifications.serverApiKeyRequired'));
        return null;
    }
    if (!isMcpServerAuthCompatibleWithTransport(transportType, authType)) {
        host.warnAndFocus(fields.authSelect, i18n.t('settings.mcp.notifications.serverAuthInvalid'));
        return null;
    }
    return {
        ...payload,
        transportType: transportType,
        authType: authType
    };
};

export { validateMcpServerForm };

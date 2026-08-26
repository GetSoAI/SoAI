/* SoAI - Settings feature MCP server JSON fields [frontend/assets/ts/features/settings/mcp/mcpServerJsonFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatNullableJsonFormValue, parseJsonFormValue } from '@core/serialization/jsonForm.ts';
import { parseOptionalJsonScalarRecordText, parseOptionalJsonStringArrayText } from '@core/serialization/json.ts';
const parseMcpServerArgumentsText = (value: string): string[] | null => {
    return parseOptionalJsonStringArrayText(value, i18n.t('settings.mcp.jsonErrors.expectedArray'));
};

const parseMcpServerScalarRecordText = (value: string): Record<string, string> | null => {
    return parseOptionalJsonScalarRecordText(value, i18n.t('settings.mcp.jsonErrors.expectedObject'));
};

const formatMcpServerJsonFieldValue = (value: string[] | Record<string, string> | null): string => {
    return formatNullableJsonFormValue(value);
};

const isMcpServerArgumentsTextValid = (value: string): boolean => {
    const result = parseJsonFormValue((text: string): string[] | null => parseMcpServerArgumentsText(text), value);
    if (!result.ok) {
        errorHandler.debug('SettingsPage', 'MCP server args JSON validation failed', result.error);
        return false;
    }
    return true;
};

const isMcpServerScalarRecordTextValid = (value: string): boolean => {
    const result = parseJsonFormValue((text: string): Record<string, string> | null => parseMcpServerScalarRecordText(text), value);
    if (!result.ok) {
        errorHandler.debug('SettingsPage', 'MCP server record JSON validation failed', result.error);
        return false;
    }
    return true;
};

export { formatMcpServerJsonFieldValue, isMcpServerArgumentsTextValid, isMcpServerScalarRecordTextValid, parseMcpServerArgumentsText, parseMcpServerScalarRecordText };

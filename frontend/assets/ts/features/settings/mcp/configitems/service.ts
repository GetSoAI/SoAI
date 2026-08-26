/* SoAI - MCP configuration tree rendering [frontend/assets/ts/features/settings/mcp/configitems/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { formatNullableJsonFormValue } from '@core/serialization/jsonForm.ts';
import { renderSettingItem, renderSettingsGroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { isBoolean, isFiniteNumber, isNullOrUndefined, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { readJsonObjectDottedPathValue } from '@core/types/payloadPathReader.ts';
import { formatSettingLabel } from '@features/settings/actions.ts';
import { createSettingInputId } from '@features/settings/configControlDescriptors.ts';
import { resolveMcpConfigHelpText } from '@features/settings/mcp/configitems/helpText.ts';

const renderScalarControl = (value: JsonValue, path: string): string => {
    const inputId = createSettingInputId(path, 'mcp');
    const escapedPath = securityApi.escapeAttribute(path);
    if (isNullOrUndefined(value)) {
        const placeholder = securityApi.escapeAttribute(i18n.t('settings.advanced.nullPlaceholder'));
        return `<input type="text" id="${inputId}" class="setting-input" data-path="${escapedPath}" placeholder="${placeholder}" value="">`;
    }
    if (isBoolean(value)) {
        return renderToggleControl({
            id: inputId,
            checked: value,
            labels: {
                trueLabel: i18n.t('settings.advanced.booleanTrue'),
                falseLabel: i18n.t('settings.advanced.booleanFalse')
            },
            inputDataset: { path }
        });
    }
    if (isNumber(value)) {
        const numberValue = isFiniteNumber(value) ? String(value) : '';
        const escapedValue = securityApi.escapeAttribute(numberValue);
        return `<input type="number" id="${inputId}" class="setting-input" data-path="${escapedPath}" value="${escapedValue}">`;
    }
    if (isString(value)) {
        const escapedValue = securityApi.escapeAttribute(value);
        if (value.includes('\n') || value.length > 100) {
            const escapedText = securityApi.escapeHtml(value);
            return `<textarea id="${inputId}" class="setting-textarea" data-path="${escapedPath}" rows="4">${escapedText}</textarea>`;
        }
        return `<input type="text" id="${inputId}" class="setting-input setting-input--wide" data-path="${escapedPath}" value="${escapedValue}">`;
    }
    const escapedJson = securityApi.escapeHtml(formatNullableJsonFormValue(value));
    return `<textarea id="${inputId}" class="setting-textarea setting-json" data-path="${escapedPath}" rows="6">${escapedJson}</textarea>`;
};

const renderConfigItem = (key: string, value: JsonValue, path: string): string => {
    return renderSettingItem({
        label: formatSettingLabel(key),
        help: resolveMcpConfigHelpText(path, key, value),
        control: renderScalarControl(value, path),
        dataset: { path }
    });
};

const renderConfigRecord = (record: JsonObject, basePath: string): string => {
    const items: string[] = [];
    const groups: string[] = [];
    for (const [key, value] of Object.entries(record)) {
        const path = `${basePath}.${key}`;
        if (isJsonObject(value) && Object.keys(value).length > 0) {
            groups.push(`<div class="settings-config-group"><h3 class="subgroup-title">${securityApi.escapeHtml(formatSettingLabel(key))}</h3>${renderConfigRecord(value, path)}</div>`);
            continue;
        }
        items.push(renderConfigItem(key, value, path));
    }
    const renderedItems = items.length > 0 ? renderSettingsGroup(items) : '';
    return `${renderedItems}${groups.join('')}`;
};

const renderConfigTreeGroup = (config: JsonObject, path: string): string => {
    const value = readJsonObjectDottedPathValue(config, path);
    if (!isJsonObject(value)) {
        throw new TypeError(`${path} must be a configuration object`);
    }
    return renderConfigRecord(value, path);
};

export { renderConfigTreeGroup };

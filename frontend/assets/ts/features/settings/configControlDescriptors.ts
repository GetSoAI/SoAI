/* SoAI - Settings configuration control descriptors [frontend/assets/ts/features/settings/configControlDescriptors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatNullableJsonFormValue } from '@core/serialization/jsonForm.ts';
import { securityApi } from '@core/security/public.ts';
import { renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { isArray, isBoolean, isFiniteNumber, isNullOrUndefined, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type SettingControlDescriptor = { controlType: 'text'; id: string; path: string; value: string; placeholder: string | null } | { controlType: 'toggle'; id: string; path: string; checked: boolean } | { controlType: 'number'; id: string; path: string; value: string } | { controlType: 'textarea'; id: string; path: string; className: string; rows: number; value: string };
type SettingControlSurface = 'advanced' | 'mcp' | 'security';

const createSettingInputId = (path: string, surface: SettingControlSurface): string => `setting_${surface}_${path.replace(/\./g, '_')}`;

const describeSettingControl = (value: JsonValue, path: string, surface: SettingControlSurface): SettingControlDescriptor => {
    const id = createSettingInputId(path, surface);
    if (isNullOrUndefined(value)) {
        return {
            controlType: 'text',
            id,
            path,
            value: '',
            placeholder: i18n.t('settings.advanced.nullPlaceholder')
        };
    }
    if (isBoolean(value)) {
        return {
            controlType: 'toggle',
            id,
            path,
            checked: Boolean(value)
        };
    }
    if (isNumber(value)) {
        return {
            controlType: 'number',
            id,
            path,
            value: isFiniteNumber(value) ? String(value) : ''
        };
    }
    if (isString(value)) {
        if (value.includes('\n') || value.length > 100) {
            return {
                controlType: 'textarea',
                id,
                path,
                className: 'setting-textarea',
                rows: 4,
                value
            };
        }
        return {
            controlType: 'text',
            id,
            path,
            value,
            placeholder: null
        };
    }
    if (isJsonObject(value) || isArray(value)) {
        return {
            controlType: 'textarea',
            id,
            path,
            className: 'setting-textarea setting-json',
            rows: 6,
            value: formatNullableJsonFormValue(value)
        };
    }
    throw new Error(`Unsupported setting control type for ${path}`);
};

const renderSettingControlMarkup = (value: JsonValue, path: string, surface: SettingControlSurface): string => {
    const descriptor = describeSettingControl(value, path, surface);
    if (descriptor.controlType === 'toggle') {
        return renderToggleControl({
            id: descriptor.id,
            checked: descriptor.checked,
            labels: {
                trueLabel: i18n.t('settings.advanced.booleanTrue'),
                falseLabel: i18n.t('settings.advanced.booleanFalse')
            },
            inputDataset: { path: descriptor.path }
        });
    }
    if (descriptor.controlType === 'textarea') {
        return `<textarea class="${securityApi.escapeAttribute(descriptor.className)}" id="${securityApi.escapeAttribute(descriptor.id)}" data-path="${securityApi.escapeAttribute(descriptor.path)}" rows="${descriptor.rows}">${securityApi.escapeHtml(descriptor.value)}</textarea>`;
    }
    if (descriptor.controlType === 'number') {
        return `<input type="number" class="setting-input" id="${securityApi.escapeAttribute(descriptor.id)}" data-path="${securityApi.escapeAttribute(descriptor.path)}" value="${securityApi.escapeAttribute(descriptor.value)}">`;
    }
    const placeholder = descriptor.placeholder === null ? '' : ` placeholder="${securityApi.escapeAttribute(descriptor.placeholder)}"`;
    return `<input type="text" class="setting-input" id="${securityApi.escapeAttribute(descriptor.id)}" data-path="${securityApi.escapeAttribute(descriptor.path)}"${placeholder} value="${securityApi.escapeAttribute(descriptor.value)}">`;
};

export { createSettingInputId, describeSettingControl, renderSettingControlMarkup };
export type { SettingControlDescriptor, SettingControlSurface };

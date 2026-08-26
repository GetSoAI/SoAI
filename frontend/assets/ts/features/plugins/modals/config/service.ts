/* SoAI - Plugin configuration modal service [frontend/assets/ts/features/plugins/modals/config/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { PLUGIN_GPU_BINDING_KEY } from '@features/plugins/modals/config/gpuBindingTypes.ts';
import type { ConfigFieldInputType, ConfigFieldMetadata, ConfigManagerHost, ConfigStructuredFieldType } from '@features/plugins/modals/config/types.ts';

const normalizePluginConfigPayload = (candidate: ApiResponsePayload): JsonObject | null => {
    if (!isJsonObject(candidate)) {
        return null;
    }
    return Object.fromEntries(Object.entries(candidate));
};

const parseConfigFieldType = (candidate: string): ConfigFieldInputType | null => {
    if (candidate === 'boolean' || candidate === 'json' || candidate === 'number' || candidate === 'string') {
        return candidate;
    }
    return null;
};

const parseStructuredFieldType = (candidate: string | undefined): ConfigStructuredFieldType | null => {
    if (candidate === 'array' || candidate === 'object') {
        return candidate;
    }
    return null;
};

const readConfigFieldMetadata = (field: HTMLInputElement | HTMLTextAreaElement): ConfigFieldMetadata | null => {
    if (!field.classList.contains('config-field')) {
        return null;
    }
    const key = field.dataset?.['key'];
    const typeRaw = field.dataset?.['type'];
    if (!key || !typeRaw) {
        return null;
    }
    const type = parseConfigFieldType(typeRaw);
    if (!type) {
        return null;
    }
    const structuredType = type === 'json' ? parseStructuredFieldType(field.dataset?.['structuredType']) : null;
    if (type === 'json' && structuredType === null) {
        return null;
    }
    return {
        key,
        type,
        structuredType,
        validationId: field.id ? `${field.id}-validation` : null
    };
};

const parseConfigFieldValue = (field: HTMLInputElement | HTMLTextAreaElement, metadata: ConfigFieldMetadata): JsonValue => {
    if (metadata.type === 'boolean') {
        if (!(field instanceof HTMLInputElement)) {
            throw new Error('Boolean config fields must be input elements');
        }
        return field.checked;
    }
    if (metadata.type === 'number') {
        if (!(field instanceof HTMLInputElement)) {
            throw new Error('Number config fields must be input elements');
        }
        const value = readFiniteInputValueOrNull(field);
        if (!field.validity.valid || value === null) {
            throw new Error(i18n.t('plugins.modal.config.invalidNumber'));
        }
        return value;
    }
    if (metadata.type === 'json') {
        let parsed: JsonValue;
        try {
            const candidate = parseRequiredJsonText(field.value);
            if (!isJsonValue(candidate)) {
                throw new Error('Value must be JSON-compatible');
            }
            parsed = candidate;
        } catch (error) {
            const message = coerceErrorMessage(error);
            throw new Error(i18n.t('plugins.modal.config.invalidJson', { message }));
        }
        if (metadata.structuredType === 'array' && !Array.isArray(parsed)) {
            throw new Error(i18n.t('plugins.modal.config.jsonArrayRequired'));
        }
        if (metadata.structuredType === 'object' && !isJsonObject(parsed)) {
            throw new Error(i18n.t('plugins.modal.config.jsonObjectRequired'));
        }
        return parsed;
    }
    return field.value;
};

const collectConfigFieldElements = (host: ConfigManagerHost, form: HTMLElement): Map<string, Element> => {
    const fieldElements = new Map<string, Element>();
    const items = host.queryUI('.config-field-item[data-config-key]', form);
    for (const item of items) {
        const configKey = item instanceof HTMLElement ? item.dataset?.['configKey'] : null;
        if (configKey) {
            fieldElements.set(configKey, item);
        }
    }
    return fieldElements;
};

const collectPluginGpuBindingFieldElements = (host: ConfigManagerHost, form: HTMLElement): Element[] => {
    return host.queryUI(`.plugin-gpu-binding-card.is-selected[data-config-key="${PLUGIN_GPU_BINDING_KEY}"]`, form);
};

export { collectConfigFieldElements, collectPluginGpuBindingFieldElements, normalizePluginConfigPayload, parseConfigFieldValue, readConfigFieldMetadata };

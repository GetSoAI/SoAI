/* SoAI - Model detail page rendering layer card sections [frontend/assets/ts/pages/modeldetail/rendering/modelDetailCardSections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { canDeleteModelRecord } from '@core/models/modelDeletionEligibility.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { MODEL_CONTEXT_WINDOW_PARAMETER_KEY, type ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { ParameterMetadata } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { Parameter } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { populateModelDetailOpenAICapabilityOverrides } from '@pages/modeldetail/controllers/openaicapabilities/effects.ts';
import { formatModelDetailDateTime, formatModelDetailDefaultValue, formatModelDetailPluginName, maskModelDetailApiUrl } from '@pages/modeldetail/formatting/modelDetailFormatting.ts';
import { renderSpecRow } from '@pages/modeldetail/rendering/layout/rendering.ts';
import { populateModelDetailEnabledToggle } from '@pages/modeldetail/state/enabled/effects.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type InfoFormatter = (value: JsonValue | null | undefined) => string | null;
type InfoField = [string, JsonValue | null | undefined, InfoFormatter?];

interface ParameterStateHost {
    getParameterKeys(): string[];
    getParameter(key: string): Parameter | null | undefined;
    getMetadata(key: string): ParameterMetadata | null | undefined;
    isParameterCustomized(key: string): boolean;
}

interface ModelDetailCardSectionsHost extends PageDomOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    parameterState: ParameterStateHost;
    sanitizeText(value: JsonValue | null | undefined): string;
    sanitizeClassName(value: string, fallback: string): string;
    setInfo(id: string, value: JsonValue | null | undefined, formatter?: InfoFormatter): void;
    getModelPluginName(): string;
    findPluginRecord(pluginName: string): PluginRecord | null;
    getDeleteModelButton(): HTMLButtonElement;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
}

const populateModelDetailExternalProviderCard = (host: ModelDetailCardSectionsHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-external-provider-card');
    if (!card) return;
    const model = host.model;
    const providerMetadataValue = model?.providerMetadata;
    const providerMetadata = isObject(providerMetadataValue) ? providerMetadataValue : null;
    if (!providerMetadata) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const fields: InfoField[] = [
        ['modeldetail-provider-name', providerMetadata['name']],
        ['modeldetail-provider-api-url', providerMetadata['apiUrl'], (value: JsonValue | null | undefined): string | null => (isString(value) ? maskModelDetailApiUrl(value) : null)],
        ['modeldetail-provider-id', providerMetadata['id']],
        ['modeldetail-provider-created', providerMetadata['createdAtMs'], (value: JsonValue | null | undefined): string | null => (isNumber(value) ? formatModelDetailDateTime(value) : null)]
    ];
    fields.forEach((field) => host.setInfo(field[0], field[1], field[2]));
    const apiUrlElement = host.pageDom.optionalHTMLElement('modeldetail-provider-api-url');
    if (apiUrlElement) {
        const apiUrl = providerMetadata['apiUrl'];
        host.pageDom.updateAttribute(apiUrlElement, 'data-copy-value', isString(apiUrl) && apiUrl ? apiUrl : null);
    }
    host.pageDom.removeClass(card, 'u-hidden');
};

const populateModelDetailPluginInfo = (host: ModelDetailCardSectionsHost): void => {
    const pluginName = host.getModelPluginName();
    host.setInfo('modeldetail-plugin', pluginName ? formatModelDetailPluginName(host.findPluginRecord(pluginName), pluginName) : null);
};

const updateModelDetailCardVisibility = (host: ModelDetailCardSectionsHost): void => {
    const descriptionRow = host.pageDom.optionalHTMLElement('modeldetail-description-row');
    if (descriptionRow) host.pageDom.toggleClass(descriptionRow, 'u-hidden', !host.model?.description);
    const pluginName = host.getModelPluginName();
    const plugin = pluginName ? host.findPluginRecord(pluginName) : null;
    host.pageDom.toggleClass(host.getDeleteModelButton(), 'u-hidden', !host.model || !canDeleteModelRecord(host.model, plugin));
};

interface ModelDetailParameterDefault {
    label: string;
    value: JsonValue;
    formatted: string;
}

const resolveModelDetailParameterDefault = (host: ModelDetailCardSectionsHost, key: string): ModelDetailParameterDefault | null => {
    const parameter = host.parameterState.getParameter(key);
    const definition = parameter?.definition;
    const hasDefault = parameter?.hasDefault ?? definition?.hasDefault ?? (definition ? 'default' in definition : false);
    if (!definition || !hasDefault || host.parameterState.isParameterCustomized(key)) {
        return null;
    }
    const value = definition.default ?? null;
    const formatted = formatModelDetailDefaultValue(value, isString(definition.type) ? definition.type : 'string');
    if (formatted === null) {
        return null;
    }
    const label = isString(definition.displayName) && definition.displayName.trim() ? definition.displayName : key;
    return { label, value, formatted };
};

const renderModelDetailDefaultRow = (host: ModelDetailCardSectionsHost, label: string, value: string): string => renderSpecRow({ label: host.sanitizeText(label), tooltip: label, value: host.sanitizeText(value), valueClassName: 'modeldetail-spec-value--numeric' });

const renderModelDetailParameterDefaultRow = (host: ModelDetailCardSectionsHost, key: string): string | null => {
    const resolved = resolveModelDetailParameterDefault(host, key);
    return resolved ? renderModelDetailDefaultRow(host, resolved.label, resolved.formatted) : null;
};

const renderModelDetailContextWindowRow = (host: ModelDetailCardSectionsHost): string | null => {
    const label = i18n.t('modelDetail.cards.inferenceDefaults.contextWindowTokens');
    const resolved = resolveModelDetailParameterDefault(host, MODEL_CONTEXT_WINDOW_PARAMETER_KEY);
    const fallback = host.model?.contextWindowTokens;
    const tokens = resolved ? resolved.value : fallback;
    if (isNumber(tokens) && Number.isFinite(tokens) && tokens > 0) {
        return renderModelDetailDefaultRow(host, label, i18n.formatNumber(Math.floor(tokens)));
    }
    return resolved ? renderModelDetailDefaultRow(host, label, resolved.formatted) : null;
};

const populateModelDetailInferenceDefaults = (host: ModelDetailCardSectionsHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-inference-defaults-card');
    const content = host.pageDom.optionalHTMLElement('modeldetail-inference-defaults');
    if (!card || !content) return;
    if (!host.model || host.isVirtualModel()) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const rows = [renderModelDetailContextWindowRow(host)]
        .concat(
            host.parameterState
                .getParameterKeys()
                .filter((key) => key !== MODEL_CONTEXT_WINDOW_PARAMETER_KEY && host.parameterState.getMetadata(key)?.group === 'inference')
                .map((key) => renderModelDetailParameterDefaultRow(host, key))
        )
        .filter((row): row is string => row !== null);
    if (rows.length === 0) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    host.pageDom.updateHtml(content, toTrustedUiHtml(rows.join('')));
    host.pageDom.removeClass(card, 'u-hidden');
};

const populateModelDetailCapabilityBadges = (host: ModelDetailCardSectionsHost): void => {
    populateModelDetailEnabledToggle(host);
    populateModelDetailOpenAICapabilityOverrides(host);
};

export { populateModelDetailCapabilityBadges, populateModelDetailExternalProviderCard, populateModelDetailInferenceDefaults, populateModelDetailPluginInfo, updateModelDetailCardVisibility };
export type { ModelDetailCardSectionsHost };

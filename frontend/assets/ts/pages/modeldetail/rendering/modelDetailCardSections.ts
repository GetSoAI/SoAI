/* SoAI - Model detail page rendering layer card sections [frontend/assets/ts/pages/modeldetail/rendering/modelDetailCardSections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatTitleFromId } from '@core/primitives/text.ts';
import { canDeleteModelRecord } from '@core/models/modelDeletionEligibility.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { MODEL_CONTEXT_WINDOW_PARAMETER_KEY, type ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { getPluginLogoPath } from '@features/catalog/public.ts';
import type { OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { ParameterMetadata } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { Parameter } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { populateModelDetailOpenAICapabilityOverrides } from '@pages/modeldetail/controllers/openaicapabilities/effects.ts';
import { formatModelDetailDateTime, formatModelDetailDefaultValue, maskModelDetailApiUrl } from '@pages/modeldetail/formatting/modelDetailFormatting.ts';
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
        ['modeldetail-provider-status', providerMetadata['status']],
        ['modeldetail-provider-created', providerMetadata['createdAtMs'], (value: JsonValue | null | undefined): string | null => (isNumber(value) ? formatModelDetailDateTime(value) : null)]
    ];
    fields.forEach((field) => host.setInfo(field[0], field[1], field[2]));
    host.pageDom.removeClass(card, 'u-hidden');
};

const populateModelDetailPluginInfoCard = (host: ModelDetailCardSectionsHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-plugin-card');
    if (!card) return;
    const pluginName = host.getModelPluginName();
    if (!pluginName) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const record = host.findPluginRecord(pluginName);
    const recordDisplayName = record && isString(record.displayName) ? record.displayName : null;
    const recordName = record && isString(record.name) ? record.name : null;
    const displayRaw = recordDisplayName || recordName || pluginName;
    const displayName = formatTitleFromId(displayRaw) || displayRaw;
    const subtitle = isString(record?.descriptionSoaiplugin) ? record.descriptionSoaiplugin.trim() : '';
    const logoPath = getPluginLogoPath(record);
    const logo = host.pageDom.optional('modeldetail-plugin-logo');
    const nameElement = host.pageDom.optionalHTMLElement('modeldetail-plugin-name');
    const subtitleElement = host.pageDom.optionalHTMLElement('modeldetail-plugin-subtitle');
    if (logo) {
        if (!(logo instanceof HTMLImageElement)) {
            throw new TypeError('#modeldetail-plugin-logo must be an HTMLImageElement');
        }
        if (logoPath) {
            host.pageDom.updateProperty(logo, 'src', logoPath);
        } else {
            logo.removeAttribute('src');
        }
        host.pageDom.updateProperty(logo, 'alt', displayName);
        host.pageDom.toggleClass(logo, 'u-hidden', !logoPath);
    }
    if (nameElement) {
        host.pageDom.updateText(nameElement, displayName);
        setTooltipText(nameElement, displayName);
    }
    if (subtitleElement) {
        host.pageDom.updateText(subtitleElement, subtitle);
        host.pageDom.toggleClass(subtitleElement, 'u-hidden', !subtitle);
    }
    const typeLabel = record?.isBuiltin === true ? i18n.t('plugins.badges.builtin') : record ? i18n.t('plugins.badges.thirdparty') : null;
    const fields: InfoField[] = [
        ['modeldetail-plugin-version', record?.versionSoaiplugin],
        ['modeldetail-plugin-author', record?.authorSoaiplugin],
        ['modeldetail-plugin-type', typeLabel],
        ['modeldetail-plugin-models', record?.stats?.modelCount, (value: JsonValue | null | undefined): string | null => (isNumber(value) ? i18n.formatNumber(value) : null)],
        ['modeldetail-plugin-providers', record?.stats?.providerCount, (value: JsonValue | null | undefined): string | null => (isNumber(value) ? i18n.formatNumber(value) : null)]
    ];
    fields.forEach((field) => host.setInfo(field[0], field[1], field[2]));
    host.pageDom.removeClass(card, 'u-hidden');
};

const updateModelDetailCardVisibility = (host: ModelDetailCardSectionsHost): void => {
    const descriptionRow = host.pageDom.optionalHTMLElement('modeldetail-description-row');
    if (descriptionRow) host.pageDom.toggleClass(descriptionRow, 'u-hidden', !host.model?.description);
    const pluginName = host.getModelPluginName();
    const plugin = pluginName ? host.findPluginRecord(pluginName) : null;
    host.pageDom.toggleClass(host.getDeleteModelButton(), 'u-hidden', !host.model || !canDeleteModelRecord(host.model, plugin));
};

const populateModelDetailInferenceDefaults = (host: ModelDetailCardSectionsHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-inference-defaults-card');
    const content = host.pageDom.optionalHTMLElement('modeldetail-inference-defaults');
    if (!card || !content) return;
    if (!host.model || host.isVirtualModel()) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const getContextWindowFallback = (): string | null => {
        const value = host.model?.contextWindowTokens;
        return isNumber(value) && Number.isFinite(value) && value > 0 ? i18n.formatNumber(Math.floor(value)) : null;
    };
    const buildDefaultRowFromParameterKey = (key: string, options?: { labelFallback?: string | null }): string | null => {
        const parameter = host.parameterState.getParameter(key);
        const parameterObject = isObject(parameter) ? parameter : null;
        const definition = parameterObject && isObject(parameterObject['definition']) ? parameterObject['definition'] : null;
        const hasDefault = parameterObject?.hasDefault ?? definition?.hasDefault ?? (definition && 'default' in definition);
        if (!definition || host.parameterState.isParameterCustomized(key) || !hasDefault) {
            return null;
        }
        const typeCandidate = definition['type'];
        const type = isString(typeCandidate) ? typeCandidate : 'string';
        const displayNameCandidate = definition.displayName;
        const label = (isString(displayNameCandidate) && displayNameCandidate.trim() ? displayNameCandidate : null) ?? options?.labelFallback ?? key;
        const defaultValue = formatModelDetailDefaultValue(definition.default ?? null, type);
        if (defaultValue === null) {
            return null;
        }
        return `<div class="modeldetail-default-row u-flex-between"><span class="modeldetail-default-label">${host.sanitizeText(label)}</span><span class="modeldetail-default-value">${host.sanitizeText(defaultValue)}</span></div>`;
    };
    const rows = host.parameterState.getParameterKeys().reduce((result: string[], key: string) => {
        if (key === MODEL_CONTEXT_WINDOW_PARAMETER_KEY) {
            return result;
        }
        const parameter = host.parameterState.getParameter(key);
        const metadata = host.parameterState.getMetadata(key);
        const parameterObject = isObject(parameter) ? parameter : null;
        const definition = parameterObject && isObject(parameterObject['definition']) ? parameterObject['definition'] : null;
        const hasDefault = parameterObject?.hasDefault ?? definition?.hasDefault ?? (definition && 'default' in definition);
        if (!definition || !isObject(metadata) || metadata['group'] !== 'inference' || host.parameterState.isParameterCustomized(key) || !hasDefault) {
            return result;
        }
        const typeCandidate = definition['type'];
        const type = isString(typeCandidate) ? typeCandidate : 'string';
        const displayNameCandidate = definition.displayName;
        const label = isString(displayNameCandidate) && displayNameCandidate.trim() ? displayNameCandidate : key;
        const defaultValue = formatModelDetailDefaultValue(definition.default ?? null, type);
        if (defaultValue !== null) {
            result.push(`<div class="modeldetail-default-row u-flex-between"><span class="modeldetail-default-label">${host.sanitizeText(label)}</span><span class="modeldetail-default-value">${host.sanitizeText(defaultValue)}</span></div>`);
        }
        return result;
    }, []);
    const contextRow =
        buildDefaultRowFromParameterKey(MODEL_CONTEXT_WINDOW_PARAMETER_KEY, { labelFallback: i18n.t('modelDetail.cards.inferenceDefaults.contextWindowTokens') }) ??
        (() => {
            const fallbackValue = getContextWindowFallback();
            if (fallbackValue === null) {
                return null;
            }
            const label = i18n.t('modelDetail.cards.inferenceDefaults.contextWindowTokens');
            return `<div class="modeldetail-default-row u-flex-between"><span class="modeldetail-default-label">${host.sanitizeText(label)}</span><span class="modeldetail-default-value">${host.sanitizeText(fallbackValue)}</span></div>`;
        })();
    if (contextRow) {
        rows.push(contextRow);
    }
    if (rows.length === 0) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const rowsMarkup = toTrustedUiHtml(rows.join(''));
    host.pageDom.updateHtml(content, rowsMarkup);
    host.pageDom.removeClass(card, 'u-hidden');
};

const populateModelDetailCapabilityBadges = (host: ModelDetailCardSectionsHost): void => {
    populateModelDetailEnabledToggle(host);
    populateModelDetailOpenAICapabilityOverrides(host);
};

export { populateModelDetailCapabilityBadges, populateModelDetailExternalProviderCard, populateModelDetailInferenceDefaults, populateModelDetailPluginInfoCard, updateModelDetailCardVisibility };
export type { ModelDetailCardSectionsHost };

/* SoAI - Model detail page widgets parameter templates rendering [frontend/assets/ts/pages/modeldetail/widgets/parametertemplates/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isArray } from '@core/typeGuards.ts';
import { securityApi } from '@core/security/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { isJsonArray, isJsonObject } from '@core/types/jsonValues.ts';
import { resolveParameterCategoryLabel } from '@pages/modeldetail/contracts/parameterCategoryMetadata.ts';
import type { NamedParameter, ParameterCollection, ParameterTemplateContext, ParameterTemplateOptions } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { resolveParameterCountBadgeTone } from '@pages/modeldetail/rendering/parameterCountBadgeTone.ts';
import { requireConfiguredIcon } from '@pages/modeldetail/guards/guards.ts';
import { renderArrayInput, renderBooleanInput, renderChoiceInput, renderNumericInput, renderObjectInput, renderTextInput } from '@pages/modeldetail/widgets/parametertemplates/parameterPresetRenderingWidget.ts';
import { createRenderContext, normalizeParameterType, resolveParameterDefinition, resolveParameterValue } from '@pages/modeldetail/widgets/parametertemplates/state.ts';

const renderParameterControlInternal = (context: ParameterTemplateContext, parameter: NamedParameter): string => {
    const { key } = parameter;
    const definition = resolveParameterDefinition(parameter.definition);
    const { type = 'string', minimum, maximum, itemType, valueCount, choices } = definition;
    const resolvedValue = resolveParameterValue(parameter, definition);
    const id = `param-input-${key}`;
    const parameterType = normalizeParameterType(type);

    if (parameterType === 'boolean') {
        return renderBooleanInput(context, {
            id,
            key,
            value: typeof resolvedValue === 'boolean' || typeof resolvedValue === 'string' ? resolvedValue : null
        });
    }

    if (parameterType === 'integer') {
        return renderNumericInput(context, {
            id,
            key,
            value: typeof resolvedValue === 'number' || typeof resolvedValue === 'string' ? resolvedValue : null,
            minimum,
            maximum,
            numericType: 'integer'
        });
    }

    if (parameterType === 'float') {
        return renderNumericInput(context, {
            id,
            key,
            value: typeof resolvedValue === 'number' || typeof resolvedValue === 'string' ? resolvedValue : null,
            minimum,
            maximum,
            numericType: 'float'
        });
    }

    if (parameterType === 'array') {
        return renderArrayInput(context, {
            id,
            key,
            value: isJsonArray(resolvedValue) ? resolvedValue : [],
            itemType,
            valueCount
        });
    }

    if (parameterType === 'object') {
        const objectValue = isJsonObject(resolvedValue) ? resolvedValue : typeof resolvedValue === 'string' ? resolvedValue : null;
        return renderObjectInput(context, {
            id,
            key,
            value: objectValue
        });
    }

    if (isArray(choices) && choices.length > 0) {
        return renderChoiceInput(context, {
            id,
            key,
            value: resolvedValue ?? undefined,
            choices
        });
    }

    return renderTextInput(context, { id, key, value: typeof resolvedValue === 'string' ? resolvedValue : '' });
};

const renderParameter = (context: ParameterTemplateContext, parameter: NamedParameter): string => {
    const { key } = parameter;
    const definition = resolveParameterDefinition(parameter.definition);
    const { displayName, category = 'other', group = 'unknown', description = '', aliases = [], requiresReload, default: defaultValue, type, itemType } = definition;
    const customized = context.isCustomized(parameter);
    const hasDefault = parameter.hasDefault ?? definition.hasDefault ?? defaultValue !== undefined;
    const badges = [customized ? `<span class="param-badge custom">${securityApi.escapeHtml(i18n.t('modelDetail.parameters.badges.custom'))}</span>` : hasDefault ? `<span class="param-badge default">${securityApi.escapeHtml(i18n.t('modelDetail.parameters.badges.default'))}</span>` : '', requiresReload ? `<span class="param-badge reload">${securityApi.escapeHtml(i18n.t('modelDetail.parameters.badges.requiresReload'))}</span>` : '', `<span class="${securityApi.escapeAttribute(`param-badge group ${group}`)}">${securityApi.escapeHtml(context.formatGroupLabel(group))}</span>`].filter(Boolean).join('');
    const aliasMarkup = aliases.length > 0 ? `<div class="parameter-aliases">${securityApi.escapeHtml(i18n.t('modelDetail.parameters.aliasesPrefix'))} ${securityApi.escapeHtml(aliases.join(', '))}</div>` : '';
    const tips: string[] = [];
    if (description) {
        tips.push(`<span class="model-parameter-help">${securityApi.escapeHtml(description)}</span>`);
    }
    if (type === 'array' && itemType) {
        tips.push(`<span class="model-parameter-help model-parameter-help-type">${securityApi.escapeHtml(context.describeArray(itemType))}</span>`);
    }
    if (type === 'object') {
        tips.push(`<span class="model-parameter-help model-parameter-help-type">${securityApi.escapeHtml(i18n.t('modelDetail.parameters.jsonObject'))}</span>`);
    }
    const helpMarkup = tips.join('');
    const label = typeof displayName === 'string' && displayName.trim().length > 0 ? displayName.trim() : key;
    return `
        <div class="model-parameter-item glass-surface-full setting-change-surface ${hasDefault ? 'default-param' : ''}" data-param="${uiAttr(key).html}" data-category="${uiAttr(category).html}" data-group="${uiAttr(group).html}">
            <div class="model-parameter-info">
                <label class="model-parameter-label">${securityApi.escapeHtml(label)}</label>
                ${aliasMarkup}
                ${helpMarkup}
                <div class="parameter-badges">${badges}</div>
            </div>
            <div class="model-parameter-control">${renderParameterControlInternal(context, parameter)}</div>
        </div>`;
};

const renderCategorySection = (context: ParameterTemplateContext, categoryKey: string, parameters: NamedParameter[]): string => {
    const label = resolveParameterCategoryLabel(context.categories?.[categoryKey], categoryKey);
    const count = parameters.length;
    const countLabel = i18n.t('modelDetail.parameters.countLabel', { count });
    const countToneClass = resolveParameterCountBadgeTone(count);
    return `
        <div class="model-parameter-section parameter-category glass-surface-full glass-surface-medium" data-category="${uiAttr(categoryKey).html}">
            <div class="card-title-bar modeldetail-category-header" data-category="${uiAttr(categoryKey).html}">
                <h3 class="card-title category-title">${securityApi.escapeHtml(label)}</h3>
                <span class="param-count ${countToneClass}">${securityApi.escapeHtml(countLabel)}</span>
            </div>
            <div class="category-content has-scroll" data-category="${uiAttr(categoryKey).html}">
                <div class="model-parameter-group">${parameters.map((parameter) => renderParameter(context, parameter)).join('')}</div>
            </div>
    </div>`;
};

const renderBackendDocumentationSection = (context: ParameterTemplateContext): string => {
    const label = i18n.t('modelDetail.buttons.backend_documentation');
    const iconMarkup = requireConfiguredIcon(context.icons, 'BACKEND_DOCUMENTATION', { subject: 'ModelDetail parameter templates', verb: 'require' });
    return `
        <div class="model-parameter-section parameter-category parameter-category--backend-doc glass-surface-full glass-surface-medium">
            <div class="card-title-bar modeldetail-category-header">
                <h3 class="card-title category-title">${i18n.t('modelDetail.parameters.backendDocumentationTitle')}</h3>
            </div>
            <div class="category-content has-scroll">
                <div class="model-parameter-doc-callout">
                    <p class="model-parameter-doc-description">${i18n.t('modelDetail.parameters.backendDocumentationDescription')}</p>
                    <a class="ui-button ui-button--sm" id="backend-doc-button" data-action="backend-documentation" target="_blank" rel="noopener noreferrer" aria-disabled="true" tabindex="-1">${iconMarkup.html}<span>${label}</span></a>
                </div>
            </div>
        </div>`;
};

const renderParametersLayout = (parameters: ParameterCollection | null | undefined, context: ParameterTemplateContext): string => {
    if (!parameters || Object.keys(parameters).length === 0) {
        return `<div class="model-parameter-layout">${renderBackendDocumentationSection(context)}</div>`;
    }

    const grouped: Record<string, NamedParameter[]> = {};
    for (const [parameterKey, parameterData] of Object.entries(parameters)) {
        const category = parameterData.definition?.category || 'other';
        (grouped[category] ??= []).push({ key: parameterKey, ...parameterData });
    }

    const sections = Object.keys(grouped)
        .map((categoryKey) => {
            const group = grouped[categoryKey];
            if (!group) {
                throw new Error(`Parameter category "${categoryKey}" is missing`);
            }
            return renderCategorySection(context, categoryKey, group);
        })
        .join('');
    return `<div class="model-parameter-layout">${renderBackendDocumentationSection(context)}${sections}</div>`;
};

const renderParametersView = (parameters: ParameterCollection | null | undefined, options: ParameterTemplateOptions): string => {
    return renderParametersLayout(parameters, createRenderContext(options));
};

const renderParameterControl = (parameter: NamedParameter, options: ParameterTemplateOptions): string => {
    return renderParameterControlInternal(createRenderContext(options), parameter);
};

export { renderParameterControl, renderParametersView };

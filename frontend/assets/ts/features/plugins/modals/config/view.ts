/* SoAI - Plugin configuration modal rendering [frontend/assets/ts/features/plugins/modals/config/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalLoadingState } from '@core/modals/scaffold.ts';
import { isBoolean, isNumber } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { renderPluginGpuBindingSelector } from '@features/plugins/modals/config/gpuBindingSelector.ts';
import { PLUGIN_GPU_BINDING_KEY, type PluginGpuBindingSelectorState } from '@features/plugins/modals/config/gpuBindingTypes.ts';
import type { SecurityService } from '@features/plugins/modals/config/types.ts';

interface RenderConfigFieldOptions {
    key: string;
    value: JsonValue;
    security: SecurityService;
}

interface RenderConfigOptions {
    gpuBindingState: PluginGpuBindingSelectorState | null;
    hideGpuBindingField: boolean;
}

const renderStructuredConfigValue = (value: JsonValue): string => {
    return JSON.stringify(value, null, 2);
};

const renderConfigField = ({ key, value, security }: RenderConfigFieldOptions): string => {
    const keyHtml = security.escapeHtml(key);
    const keyAttr = security.escapeAttribute(key);
    const configIdAttr = `config-${keyAttr}`;
    let inputHtml: string;
    let fullWidth = false;

    if (Array.isArray(value) || isJsonObject(value)) {
        fullWidth = true;
        const structuredType = Array.isArray(value) ? 'array' : 'object';
        inputHtml = `<textarea id="${configIdAttr}" class="form-input config-field setting-json" data-key="${keyAttr}" data-type="json" data-structured-type="${structuredType}" rows="8">${security.escapeHtml(renderStructuredConfigValue(value))}</textarea><div class="form-help">${i18n.t('plugins.modal.config.jsonHelp')}</div><div class="plugin-config-validation" id="${configIdAttr}-validation" aria-live="polite"></div>`;
    } else if (isBoolean(value)) {
        inputHtml = `<input type="checkbox" id="${configIdAttr}" class="config-field" data-key="${keyAttr}" data-type="boolean" ${value ? 'checked' : ''}>`;
    } else if (isNumber(value)) {
        inputHtml = `<input type="number" id="${configIdAttr}" class="form-input config-field" data-key="${keyAttr}" data-type="number" value="${security.escapeAttribute(String(value))}">`;
    } else {
        inputHtml = `<input type="text" id="${configIdAttr}" class="form-input config-field" data-key="${keyAttr}" data-type="string" value="${security.escapeAttribute(String(value ?? ''))}">`;
    }

    const classes = ['form-group', 'config-field-item', 'setting-change-surface'];
    if (fullWidth) {
        classes.push('config-field-item--full');
    }

    return `<div class="${classes.join(' ')}" data-config-key="${keyAttr}"><label for="${configIdAttr}">${keyHtml}</label>${inputHtml}</div>`;
};

const renderConfigLoadingMarkup = (): TrustedHtml => renderModalLoadingState({ text: i18n.t('plugins.modal.config.loading') });

const renderPluginConfigFieldsSection = (configMarkup: string, showHeader: boolean): string => {
    const headerMarkup = showHeader ? `<div class="plugin-config-fields-header"><label class="plugin-config-section-label plugin-config-fields-title">${i18n.t('plugins.modal.config.fieldsTitle')}</label><div class="form-help plugin-config-fields-subtitle">${i18n.t('plugins.modal.config.fieldsSubtitle')}</div></div>` : '';
    return `<section class="plugin-config-fields-section">${headerMarkup}${configMarkup}</section>`;
};

const renderConfigWithGpuBindingMarkup = (security: SecurityService, configMarkup: string, options: RenderConfigOptions): TrustedHtml => {
    return toTrustedUiHtml(`${renderPluginGpuBindingSelector(options.gpuBindingState, security)}${renderPluginConfigFieldsSection(configMarkup, options.gpuBindingState !== null)}`);
};

const renderConfigEmptyMarkup = (security: SecurityService, options: RenderConfigOptions): TrustedHtml => {
    return renderConfigWithGpuBindingMarkup(security, `<p class="form-help">${i18n.t('plugins.modal.config.noConfig')}</p>`, options);
};

const renderConfigGridMarkup = (config: JsonObject, security: SecurityService, options: RenderConfigOptions): TrustedHtml => {
    const fields = Object.entries(config)
        .filter(([key]) => !options.hideGpuBindingField || key !== PLUGIN_GPU_BINDING_KEY)
        .map(([key, value]) => renderConfigField({ key, value, security }))
        .join('');
    return renderConfigWithGpuBindingMarkup(security, `<div class="plugin-config-grid">${fields}</div>`, options);
};

export { renderConfigEmptyMarkup, renderConfigGridMarkup, renderConfigLoadingMarkup };

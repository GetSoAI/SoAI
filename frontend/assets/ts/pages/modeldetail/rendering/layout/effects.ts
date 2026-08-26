/* SoAI - Model detail page rendering layer layout effects [frontend/assets/ts/pages/modeldetail/rendering/layout/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { EXTERNAL_PROVIDER_ROWS, IDENTITY_ROWS, METRICS_ROWS, PLUGIN_ROWS, STATUS_ROWS, TECHNICAL_ROWS } from '@pages/modeldetail/rendering/layout/constants.ts';
import { renderCard, renderRows } from '@pages/modeldetail/rendering/layout/rendering.ts';

const renderIdentityCard = (): string => {
    return renderCard({
        id: 'modeldetail-identity-card',
        title: i18n.t('modelDetail.cards.identity.title'),
        content: renderRows('info', IDENTITY_ROWS)
    });
};

const renderTechnicalCard = (): string => {
    const rows = renderRows('info', TECHNICAL_ROWS);
    const descriptionRow = `<div class="modeldetail-info-row modeldetail-info-row--fullwidth u-hidden" id="modeldetail-description-row">
    <span class="modeldetail-info-label">${i18n.t('modelDetail.cards.technical.description')}</span>
    <span class="modeldetail-info-value" id="modeldetail-description"></span>
    </div>`;
    return renderCard({
        id: 'modeldetail-technical-card',
        title: i18n.t('modelDetail.cards.technical.title'),
        content: rows + descriptionRow
    });
};

const renderStatusCard = (): string => {
    const renderStatusButton = (label: string, id: string, action: string, variant = '', extraClass = ''): string => {
        const standardClass = variant ? '' : '';
        return `<button type="button" class="ui-button ui-button--sm${standardClass}${variant} ${extraClass}" id="${id}" data-action="${action}" ${renderLabelAttributes(label)}>${label}</button>`;
    };
    const renderStopPluginButton = (): string => {
        const label = i18n.t('modelDetail.cards.status.stopPlugin');
        const icon = renderIconSlot(getIconSync('stop', { size: 16, strokeWidth: 1.5 }));
        return `<button type="button" class="ui-button ui-button--sm ui-icon-button ui-variant-danger u-hidden" id="stop-plugin" data-action="stop-plugin" ${renderLabelAttributes(label)}>${icon}</button>`;
    };

    const rows = renderRows('info', STATUS_ROWS);
    const enabledToggle = `<div class="modeldetail-enabled-toggle u-hidden" id="modeldetail-enabled-toggle">
    <label class="toggle-switch toggle-switch--inline modeldetail-enabled-toggle-switch" id="modeldetail-enabled-toggle-switch" data-action="toggle-model-enabled">
    <input type="checkbox" id="modeldetail-enabled-checkbox">
    <span class="slider"></span>
    <span class="toggle-label">${i18n.t('modelDetail.cards.status.enabledToggleLabel')}</span>
    </label>
    <div class="modeldetail-enabled-note">${i18n.t('modelDetail.cards.status.enabledNote')}</div>
    </div>`;
    const actions = `<div class="modeldetail-status-actions">
    ${renderStatusButton(i18n.t('modelDetail.cards.status.manageAlias'), 'manage-alias', 'manage-alias')}
    ${renderStatusButton(i18n.t('modelDetail.cards.status.parameters'), 'switch-to-parameters', 'switch-to-parameters')}
    ${renderStatusButton(i18n.t('modelDetail.cards.status.delete'), 'delete-model', 'delete-model', ' ui-variant-danger')}
    ${renderStopPluginButton()}
    </div>`;
    return renderCard({
        id: 'modeldetail-status-card',
        title: i18n.t('modelDetail.cards.status.title'),
        content: rows + enabledToggle + actions
    });
};

const renderCapabilitiesCard = (): string => {
    const title = i18n.t('modelDetail.cards.capabilities.title');
    const resetLabel = i18n.t('modelDetail.cards.capabilities.reset');
    const saveLabel = i18n.t('common.save');
    const resetIcon = renderIconSlot(getIconSync('close', { size: 14, strokeWidth: 1.6 }));
    const saveIcon = renderIconSlot(getIconSync('save', { size: 14, strokeWidth: 1.6 }));
    return `
    <div class="modeldetail-card glass-surface-full modeldetail-status-capabilities u-hidden" id="modeldetail-status-capabilities">
    <div class="modeldetail-card-header">
    <div class="modeldetail-status-capabilities-heading">
    <h3 class="modeldetail-card-title">${title}</h3>
    </div>
    <button type="button" class="ui-button ui-button--titlebar ui-variant-accent modeldetail-status-capabilities-save u-hidden" id="modeldetail-openai-capabilities-save" data-action="save-parameters" ${renderLabelAttributes(saveLabel)}>${saveIcon}<span>${saveLabel}</span></button>
    <button type="button" class="ui-button ui-button--titlebar ui-variant-neutral modeldetail-status-capabilities-reset" id="modeldetail-openai-capabilities-reset" data-openai-capability-reset="true" data-action="reset-openai-capabilities" ${renderLabelAttributes(resetLabel)}>${resetIcon}<span>${resetLabel}</span></button>
    </div>
    <div class="modeldetail-card-body">
    <div class="modeldetail-capabilities" id="modeldetail-status-capabilities-list"></div>
    </div>
    </div>`;
};

const renderPluginCard = (): string => {
    const rows = renderRows('info', PLUGIN_ROWS);
    const pluginSummary = `<div class="modeldetail-plugin-summary">
        <img class="plugin-logo-small modeldetail-plugin-logo" id="modeldetail-plugin-logo" alt="">
        <div class="modeldetail-plugin-meta">
        <div class="modeldetail-plugin-name" id="modeldetail-plugin-name"></div>
        <div class="modeldetail-plugin-subtitle u-hidden" id="modeldetail-plugin-subtitle"></div>
        </div>
        </div>`;
    return renderCard({
        id: 'modeldetail-plugin-card',
        title: i18n.t('modelDetail.cards.plugin.title'),
        content: `${pluginSummary}${rows}`
    });
};

const renderMetricsCard = (): string => {
    return renderCard({
        id: 'modeldetail-metrics-card',
        title: i18n.t('modelDetail.cards.metrics.title'),
        content: renderRows('metrics', METRICS_ROWS)
    });
};

const renderExternalProviderCard = (): string => {
    return renderCard({
        id: 'modeldetail-external-provider-card',
        title: i18n.t('modelDetail.cards.externalProvider.title'),
        content: renderRows('info', EXTERNAL_PROVIDER_ROWS),
        hidden: true
    });
};

const renderInferenceDefaultsCard = (): string => {
    return renderCard({
        id: 'modeldetail-inference-defaults-card',
        title: i18n.t('modelDetail.cards.inferenceDefaults.title'),
        content: '<div class="modeldetail-inference-defaults" id="modeldetail-inference-defaults"></div>',
        hidden: true
    });
};

const renderConstituentsCard = (): string => {
    return renderCard({
        id: 'modeldetail-constituents-card',
        title: i18n.t('modelDetail.cards.constituents.title'),
        content: '<div class="modeldetail-constituent-list" id="modeldetail-constituent-list"></div>',
        hidden: true
    });
};

export { renderCapabilitiesCard, renderConstituentsCard, renderExternalProviderCard, renderIdentityCard, renderInferenceDefaultsCard, renderMetricsCard, renderPluginCard, renderStatusCard, renderTechnicalCard };

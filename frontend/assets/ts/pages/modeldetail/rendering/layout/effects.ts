/* SoAI - Model detail page rendering layer layout effects [frontend/assets/ts/pages/modeldetail/rendering/layout/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, securityApi } from '@core/security/public.ts';
import { renderSettingItem } from '@core/settings/settingsMarkup.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { ACTION_DELETE_MODEL, ACTION_MANAGE_ALIAS, ACTION_STOP_PLUGIN, ACTION_TOGGLE_MODEL_ENABLED } from '@features/modeldetail/public.ts';
import { DETAIL_ROWS, EXTERNAL_PROVIDER_ROWS, STATUS_ROWS } from '@pages/modeldetail/rendering/layout/constants.ts';
import { MODEL_DETAIL_FACT_CLASS, renderCard, renderSpecRow, renderSpecRows } from '@pages/modeldetail/rendering/layout/rendering.ts';

const renderActionButton = (options: { id: string; action: string; label: string; variant: string; icon?: IconName; hidden?: boolean }): string => {
    const icon = options.icon ? renderIconSlot(getIconSync(options.icon, { size: 14, strokeWidth: 1.6 })).html : '';
    const className = ['ui-button', 'ui-button--sm', options.variant, options.hidden ? 'u-hidden' : ''].filter(Boolean).join(' ');
    return `<button type="button" class="${className}" id="${options.id}" data-action="${options.action}" ${renderLabelAttributes(options.label).html}>${icon}<span>${options.label}</span></button>`;
};

const renderStatusRow = (options: { nameId: string; label: string; statusId: string; statusLabel: string; copyable?: boolean }): string =>
    renderSpecRow({
        id: options.nameId,
        label: options.label,
        copyable: options.copyable,
        hidden: true,
        trailing: `<span class="ui-status-badge ${MODEL_DETAIL_FACT_CLASS} u-hidden" id="${options.statusId}-row" data-tooltip="${securityApi.escapeAttribute(options.statusLabel)}"><span id="${options.statusId}"></span></span>`
    });

const renderDetailsCard = (): string => {
    const description = `<p class="modeldetail-description ${MODEL_DETAIL_FACT_CLASS} u-hidden" id="modeldetail-description-row"><span id="modeldetail-description"></span></p>`;
    return renderCard({
        id: 'modeldetail-details-card',
        title: i18n.t('modelDetail.cards.technical.title'),
        content: `${description}<dl class="modeldetail-spec">${renderSpecRows(DETAIL_ROWS)}</dl>`,
        className: 'modeldetail-details-card'
    });
};

const renderStatusCard = (): string => {
    const enabledLabel = i18n.t('modelDetail.cards.status.enabledToggleLabel');
    const enabledToggle = renderSettingItem({
        label: enabledLabel,
        help: i18n.t('modelDetail.cards.status.enabledNote'),
        control: renderToggleSwitch({
            id: 'modeldetail-enabled-checkbox',
            checked: false,
            labels: { trueLabel: i18n.t('common.enabled'), falseLabel: i18n.t('common.disabled') },
            showLabel: false,
            ariaLabel: enabledLabel,
            wrapperDataset: { action: ACTION_TOGGLE_MODEL_ENABLED }
        }),
        className: 'modeldetail-enabled-toggle u-hidden',
        attributes: { id: 'modeldetail-enabled-toggle' }
    });
    const actions = [renderActionButton({ id: ACTION_MANAGE_ALIAS, action: ACTION_MANAGE_ALIAS, label: i18n.t('modelDetail.cards.status.manageAlias'), variant: 'ui-variant-neutral' }), renderActionButton({ id: ACTION_STOP_PLUGIN, action: ACTION_STOP_PLUGIN, label: i18n.t('modelDetail.cards.status.stopPlugin'), variant: 'ui-variant-warning', icon: 'stop', hidden: true }), renderActionButton({ id: ACTION_DELETE_MODEL, action: ACTION_DELETE_MODEL, label: i18n.t('modelDetail.cards.status.delete'), variant: 'ui-variant-danger' })].join('');
    const pluginRow = renderStatusRow({ nameId: 'modeldetail-plugin', label: i18n.t('modelDetail.cards.plugin.title'), statusId: 'modeldetail-plugin-status', statusLabel: i18n.t('modelDetail.cards.status.title') });
    return renderCard({
        id: 'modeldetail-status-card',
        title: i18n.t('modelDetail.cards.status.title'),
        content: `<dl class="modeldetail-spec">${pluginRow}${renderSpecRows(STATUS_ROWS)}</dl>${enabledToggle}<div class="modeldetail-card-actions">${actions}</div>`,
        className: 'modeldetail-status-card',
        bodyClassName: 'modeldetail-card-body--stack'
    });
};

const renderExternalProviderCard = (): string =>
    renderCard({
        id: 'modeldetail-external-provider-card',
        title: i18n.t('modelDetail.cards.externalProvider.title'),
        content: `<dl class="modeldetail-spec">${renderSpecRow({ id: 'modeldetail-provider-name', label: i18n.t('modelDetail.cards.externalProvider.name'), copyable: true, hidden: true })}${renderSpecRows(EXTERNAL_PROVIDER_ROWS)}</dl>`,
        bodyClassName: 'modeldetail-card-body--stack',
        hidden: true
    });

const renderInferenceDefaultsCard = (): string =>
    renderCard({
        id: 'modeldetail-inference-defaults-card',
        title: i18n.t('modelDetail.cards.inferenceDefaults.title'),
        content: '<dl class="modeldetail-spec modeldetail-spec--columns modeldetail-inference-defaults" id="modeldetail-inference-defaults"></dl>',
        hidden: true
    });

const renderConstituentsCard = (): string =>
    renderCard({
        id: 'modeldetail-constituents-card',
        title: i18n.t('modelDetail.cards.constituents.title'),
        content: '<dl class="modeldetail-spec modeldetail-constituent-list" id="modeldetail-constituent-list"></dl>',
        hidden: true
    });

const renderCapabilitiesCard = (): string =>
    renderCard({
        id: 'modeldetail-status-capabilities',
        title: i18n.t('modelDetail.cards.capabilities.title'),
        content: '<div class="modeldetail-capabilities" id="modeldetail-status-capabilities-list"></div>',
        className: 'modeldetail-status-capabilities',
        hidden: true
    });

export { renderCapabilitiesCard, renderConstituentsCard, renderDetailsCard, renderExternalProviderCard, renderInferenceDefaultsCard, renderStatusCard };

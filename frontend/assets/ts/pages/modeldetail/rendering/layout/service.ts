/* SoAI - Model detail page rendering layer layout service [frontend/assets/ts/pages/modeldetail/rendering/layout/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { FILTER_OPTIONS } from '@pages/modeldetail/rendering/layout/constants.ts';
import { renderCapabilitiesCard, renderConstituentsCard, renderExternalProviderCard, renderIdentityCard, renderInferenceDefaultsCard, renderMetricsCard, renderPluginCard, renderStatusCard, renderTechnicalCard } from '@pages/modeldetail/rendering/layout/effects.ts';
import type { HeaderActionDefinition, HeaderConfig } from '@pages/modeldetail/rendering/layout/types.ts';

const buildHeaderConfig = (): HeaderConfig => {
    const renderButton = (id: string, action: string, label: string, variant = '', hidden = true) => {
        const className = `ui-button ${variant}${hidden ? ' u-hidden' : ''}`;
        return uiHtml`<button type="button" class="${uiAttr(className)}" id="${uiAttr(id)}" data-action="${uiAttr(action)}" ${renderLabelAttributes(label)}>${label}</button>`;
    };

    const actions: HeaderActionDefinition[] = [
        { type: 'search', class: 'u-hidden' },
        {
            type: 'filter',
            class: 'u-hidden',
            filter: {
                type: 'select',
                id: 'param-unified-filter',
                options: FILTER_OPTIONS.map((option) => ({ value: option.value, label: option.getLabel() }))
            }
        },
        { type: 'custom', html: renderButton('test-model-header', 'test-model', i18n.t('modelDetail.buttons.test'), 'ui-variant-primary', false) },
        {
            type: 'custom',
            html: renderButton('reset-all-params-header', 'reset-all-parameters', i18n.t('modelDetail.buttons.resetAll'), 'ui-variant-danger')
        },
        {
            type: 'custom',
            html: renderButton('save-params-header', 'save-parameters', i18n.t('modelDetail.buttons.saveParameters'), 'ui-variant-accent')
        }
    ];

    return {
        containerClass: 'model-detail-container page-scrollable',
        title: i18n.t('modelDetail.loading'),
        description: i18n.t('modelDetail.loadingDetails'),
        floating: true,
        contentLayout: 'sections',
        actions,
        tabs: {
            containerId: 'model-tabs-container',
            html: EMPTY_UI_HTML
        },
        responsive: { mobile: { stackActions: true, hideElements: [] } }
    };
};

const renderContent = (): string => {
    return `
    <div class="tab-content is-active" id="overview-content">
    <div class="modeldetail-overview-grid">
    ${renderStatusCard()}${renderCapabilitiesCard()}${renderPluginCard()}${renderIdentityCard()}
    ${renderTechnicalCard()}${renderInferenceDefaultsCard()}${renderMetricsCard()}${renderExternalProviderCard()}${renderConstituentsCard()}
    </div>
    </div>
    <div class="tab-content" id="parameters-content"><div id="parameters-interface" class="parameters-interface"></div></div>
    <div class="model-detail-error u-hidden" id="model-detail-error">
    <div class="error-state">
    <div class="error-icon"></div>
    <h3>${i18n.t('modelDetail.error.notFound')}</h3>
    <p>${i18n.t('modelDetail.error.notFoundMessage')}</p>
    <button type="button" class="ui-button ui-variant-neutral" id="back-to-models-error" data-action="back-to-models" ${renderLabelAttributes(i18n.t('modelDetail.error.backToModels'))}>${i18n.t('modelDetail.error.backToModels')}</button>
    </div>
    </div>
    `;
};

export { buildHeaderConfig, renderContent };

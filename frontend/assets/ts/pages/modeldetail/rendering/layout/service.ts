/* SoAI - Model detail page rendering layer layout service [frontend/assets/ts/pages/modeldetail/rendering/layout/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { SUMMARY_ROWS } from '@pages/modeldetail/rendering/layout/constants.ts';
import { renderCapabilitiesCard, renderConstituentsCard, renderDetailsCard, renderExternalProviderCard, renderInferenceDefaultsCard, renderStatusCard } from '@pages/modeldetail/rendering/layout/effects.ts';
import type { HeaderActionDefinition, HeaderConfig } from '@pages/modeldetail/rendering/layout/types.ts';

const buildHeaderConfig = (): HeaderConfig => {
    const renderButton = (id: string, action: string, label: string, variant: string, hidden: boolean) => {
        const className = `ui-button ${variant}${hidden ? ` ${CSS_CLASSES.HIDDEN}` : ''}`;
        return uiHtml`<button type="button" class="${uiAttr(className)}" id="${uiAttr(id)}" data-action="${uiAttr(action)}" ${action === 'reset-openai-capabilities' ? uiHtml`data-openai-capability-reset="true"` : EMPTY_UI_HTML} ${renderLabelAttributes(label)}>${label}</button>`;
    };

    const actions: HeaderActionDefinition[] = [
        { type: 'search', class: CSS_CLASSES.HIDDEN },
        { type: 'custom', html: renderButton('modeldetail-openai-capabilities-reset', 'reset-openai-capabilities', i18n.t('modelDetail.buttons.resetAll'), 'ui-variant-danger', false) },
        { type: 'custom', html: renderButton('reset-all-params-header', 'reset-all-parameters', i18n.t('modelDetail.buttons.resetAll'), 'ui-variant-danger', true) },
        { type: 'custom', html: renderButton('save-params-header', 'save-parameters', i18n.t('modelDetail.buttons.saveParameters'), 'ui-variant-accent', false) },
        { type: 'custom', html: renderButton('test-model-header', 'test-model', i18n.t('modelDetail.buttons.test'), 'ui-variant-primary', false) }
    ];

    return {
        containerClass: 'model-detail-container page-scrollable',
        title: i18n.t('modelDetail.loading'),
        description: i18n.t('modelDetail.loadingDetails'),
        floating: true,
        contentLayout: 'sections',
        actions,
        stats: SUMMARY_ROWS.map((row) => ({ id: row.id, label: row.getLabel() })),
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
    <div class="modeldetail-overview-main">${renderDetailsCard()}${renderConstituentsCard()}${renderInferenceDefaultsCard()}${renderCapabilitiesCard()}</div>
    <aside class="modeldetail-overview-side">${renderStatusCard()}${renderExternalProviderCard()}</aside>
    </div>
    </div>
    <div class="tab-content" id="parameters-content"><div id="parameters-availability" class="parameters-availability u-hidden" role="status" aria-live="polite"></div><div id="parameters-interface" class="parameters-interface"></div></div>
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

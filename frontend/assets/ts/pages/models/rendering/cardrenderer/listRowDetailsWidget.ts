/* SoAI - Models page list row details widget [frontend/assets/ts/pages/models/rendering/cardrenderer/listRowDetailsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_METRIC_BADGE } from '@core/models/pageActions.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { capitalize } from '@core/primitives/text.ts';
import { isArray } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { renderAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import type { ModelCardHost } from '@pages/models/rendering/cardrenderer/types.ts';

interface ListFact {
    key: string;
    label: string;
    value: string | number;
    compactValue?: string | undefined;
    clickable: boolean;
}

const renderListFact = (fact: ListFact, host: ModelCardHost): string => {
    const tag = fact.clickable ? 'button' : 'span';
    const typeAttribute = fact.clickable ? ' type="button"' : '';
    const actionAttribute = fact.clickable ? ` data-action="${MODELS_ACTION_METRIC_BADGE}"` : '';
    const value = fact.compactValue ? renderAdaptiveNumber(String(fact.value), fact.compactValue) : host.presentation.sanitizeText(String(fact.value ?? ''));
    return `<${tag}${typeAttribute} class="ui-collection-list__fact${fact.clickable ? ' ui-collection-list__fact--action' : ''}"${actionAttribute} data-metric-key="${host.sanitizeClassName(fact.key, 'metric')}"><span class="ui-metric-label">${host.presentation.sanitizeText(fact.label)}</span><span class="ui-metric-value">${value}</span></${tag}>`;
};

const buildModelListMetrics = (model: ModelData, host: ModelCardHost): string => {
    const requestCount = host.metrics.formatNumber(host.metrics.resolveModelRequestCount(model));
    const typeLabel = model.type === 'local' ? i18n.t('models.types.local') : capitalize(model.type || i18n.t('models.types.unknown'));
    const commonFacts: ListFact[] = [
        {
            key: 'PARAMETERS',
            label: i18n.t('models.metrics.parameters'),
            value: model.modelHasCustomParameters ? i18n.t('models.metrics.custom') : i18n.t('models.metrics.default'),
            clickable: true
        },
        { key: 'REQUESTS', label: i18n.t('models.metrics.requests'), value: requestCount, clickable: true },
        { key: 'TYPE', label: i18n.t('models.metrics.type'), value: typeLabel, clickable: false }
    ];

    if (model.type === 'virtual') {
        const count = isArray(model.models) ? model.models.length : model.constituents || 0;
        return [
            { key: 'STRATEGY', label: i18n.t('models.metrics.strategy'), value: host.metrics.formatStrategyLabel(model.strategy), clickable: false },
            { key: 'CONSTITUENT_MODELS', label: i18n.t('models.metrics.constituentModelsShort'), value: count || 0, clickable: false },
            { key: 'REQUESTS', label: i18n.t('models.metrics.requests'), value: requestCount, clickable: false }
        ]
            .map((fact) => renderListFact(fact, host))
            .join('');
    }

    if (host.status.isExternalProviderModel(model)) {
        const tokens = host.metrics.resolveModelTokenCount(model);
        return [{ key: 'TOKENS', label: i18n.t('models.metrics.tokens'), value: host.metrics.formatNumber(tokens), compactValue: formatCompactNumber(tokens), clickable: true }, ...commonFacts].map((fact) => renderListFact(fact, host)).join('');
    }

    return [{ key: 'MODEL_SIZE', label: i18n.t('models.metrics.modelSize'), value: formatBytes(model.sizeBytes), clickable: true }, ...commonFacts].map((fact) => renderListFact(fact, host)).join('');
};

const buildModelListStatus = (label: string, className: string, host: ModelCardHost): string => `<span class="ui-collection-list__status ${host.sanitizeClassName(className, 'status-neutral')}"><span class="status-led status-led-sm status-led-no-margin" aria-hidden="true"></span><span>${host.presentation.sanitizeText(label)}</span></span>`;

export { buildModelListMetrics, buildModelListStatus };

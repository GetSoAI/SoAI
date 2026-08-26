/* SoAI - Model detail page rendering layer layout constants [frontend/assets/ts/pages/modeldetail/rendering/layout/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { FilterOptionDefinition, RowDefinition } from '@pages/modeldetail/rendering/layout/types.ts';

const FILTER_OPTIONS: readonly FilterOptionDefinition[] = Object.freeze([
    { value: 'all', getLabel: (): string => i18n.t('modelDetail.filters.allParameters') },
    { value: 'group:startup', getLabel: (): string => i18n.t('modelDetail.filters.groupStartup') },
    { value: 'group:inference', getLabel: (): string => i18n.t('modelDetail.filters.groupInference') }
]);

const IDENTITY_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-display-name', className: '', getLabel: (): string => i18n.t('modelDetail.cards.identity.display_name') },
    { id: 'modeldetail-source-model-id', className: 'modeldetail-info-value--mono', getLabel: (): string => i18n.t('modelDetail.cards.identity.source_model_id') },
    { id: 'modeldetail-universal-id', className: 'modeldetail-info-value--mono', getLabel: (): string => i18n.t('modelDetail.cards.identity.universal_id') },
    { id: 'modeldetail-provider', className: '', getLabel: (): string => i18n.t('modelDetail.cards.identity.provider') },
    { id: 'modeldetail-type', className: '', getLabel: (): string => i18n.t('modelDetail.cards.identity.type') }
]);

const TECHNICAL_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-repository', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.repository') },
    { id: 'modeldetail-path', className: 'modeldetail-info-value--path', getLabel: (): string => i18n.t('modelDetail.cards.technical.path') },
    { id: 'modeldetail-size', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.size') },
    { id: 'modeldetail-family', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.family') },
    { id: 'modeldetail-quantization', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.quantization') },
    { id: 'modeldetail-license', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.license') },
    { id: 'modeldetail-created', className: '', getLabel: (): string => i18n.t('modelDetail.cards.technical.created') }
]);

const STATUS_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-model-status', getLabel: (): string => i18n.t('modelDetail.cards.status.modelStatus') },
    { id: 'modeldetail-available', getLabel: (): string => i18n.t('modelDetail.cards.status.available') },
    { id: 'modeldetail-orphaned', getLabel: (): string => i18n.t('modelDetail.cards.status.orphaned') }
]);

const PLUGIN_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-plugin-status', getLabel: (): string => i18n.t('modelDetail.cards.plugin.plugin_status') },
    { id: 'modeldetail-plugin-version', getLabel: (): string => i18n.t('modelDetail.cards.plugin.version') },
    { id: 'modeldetail-plugin-author', getLabel: (): string => i18n.t('modelDetail.cards.plugin.author') },
    { id: 'modeldetail-plugin-type', getLabel: (): string => i18n.t('modelDetail.cards.plugin.type') },
    { id: 'modeldetail-plugin-models', getLabel: (): string => i18n.t('modelDetail.cards.plugin.models') },
    { id: 'modeldetail-plugin-providers', getLabel: (): string => i18n.t('modelDetail.cards.plugin.providers') }
]);

const METRICS_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-total-requests', rowClassName: 'modeldetail-metrics-row--total-requests', getLabel: (): string => i18n.t('modelDetail.cards.metrics.totalRequests') },
    { id: 'modeldetail-tokens-generated', getLabel: (): string => i18n.t('modelDetail.cards.metrics.tokensGenerated') },
    {
        id: 'modeldetail-modality-usage',
        getLabel: (): string => i18n.t('modelDetail.cards.metrics.modalityUsage')
    },
    { id: 'modeldetail-avg-tokens', getLabel: (): string => i18n.t('modelDetail.cards.metrics.avgTokens') },
    { id: 'modeldetail-success-rate', getLabel: (): string => i18n.t('modelDetail.cards.metrics.success_rate') },
    { id: 'modeldetail-failed-requests', getLabel: (): string => i18n.t('modelDetail.cards.metrics.failedRequests') },
    { id: 'modeldetail-avg-latency', getLabel: (): string => i18n.t('modelDetail.cards.metrics.avgLatency') },
    { id: 'modeldetail-wait-time', getLabel: (): string => i18n.t('modelDetail.cards.metrics.waitTime') },
    { id: 'modeldetail-last-used', getLabel: (): string => i18n.t('modelDetail.cards.metrics.last_used') }
]);

const EXTERNAL_PROVIDER_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-provider-name', className: '', getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.name') },
    { id: 'modeldetail-provider-api-url', className: 'modeldetail-info-value--mono', getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.api_url') },
    { id: 'modeldetail-provider-id', className: 'modeldetail-info-value--mono', getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.providerId') },
    { id: 'modeldetail-provider-status', className: '', getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.status') },
    { id: 'modeldetail-provider-created', className: '', getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.created') }
]);

export { EXTERNAL_PROVIDER_ROWS, FILTER_OPTIONS, IDENTITY_ROWS, METRICS_ROWS, PLUGIN_ROWS, STATUS_ROWS, TECHNICAL_ROWS };

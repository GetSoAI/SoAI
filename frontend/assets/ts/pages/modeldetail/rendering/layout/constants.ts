/* SoAI - Model detail page rendering layer layout constants [frontend/assets/ts/pages/modeldetail/rendering/layout/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { RowDefinition } from '@pages/modeldetail/rendering/layout/types.ts';

const DETAIL_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-display-name', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.identity.display_name') },
    { id: 'modeldetail-family', getLabel: (): string => i18n.t('modelDetail.cards.technical.family') },
    { id: 'modeldetail-license', getLabel: (): string => i18n.t('modelDetail.cards.technical.license') },
    { id: 'modeldetail-source-model-id', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.identity.source_model_id') },
    { id: 'modeldetail-universal-id', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.identity.universal_id') },
    { id: 'modeldetail-repository', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.technical.repository') },
    { id: 'modeldetail-path', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.technical.path') }
]);

const STATUS_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-type', getLabel: (): string => i18n.t('modelDetail.cards.identity.type') },
    { id: 'modeldetail-available', getLabel: (): string => i18n.t('modelDetail.cards.status.available') },
    { id: 'modeldetail-created', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.technical.created') },
    { id: 'modeldetail-orphaned', getLabel: (): string => i18n.t('modelDetail.cards.status.orphaned') },
    { id: 'modeldetail-avg-tokens', getLabel: (): string => i18n.t('modelDetail.cards.metrics.avgTokens') },
    { id: 'modeldetail-success-rate', getLabel: (): string => i18n.t('modelDetail.cards.metrics.success_rate') },
    { id: 'modeldetail-modality-usage', getLabel: (): string => i18n.t('modelDetail.cards.metrics.modalityUsage') }
]);

const SUMMARY_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-model-status', getLabel: (): string => i18n.t('modelDetail.cards.status.modelStatus') },
    { id: 'modeldetail-size', suppressWhenEmpty: true, getLabel: (): string => i18n.t('modelDetail.cards.technical.size') },
    { id: 'modeldetail-quantization', suppressWhenEmpty: true, getLabel: (): string => i18n.t('modelDetail.cards.technical.quantization') },
    { id: 'modeldetail-total-requests', getLabel: (): string => i18n.t('modelDetail.cards.metrics.totalRequests') },
    { id: 'modeldetail-tokens-generated', getLabel: (): string => i18n.t('modelDetail.cards.metrics.tokensGenerated') },
    { id: 'modeldetail-last-used', suppressWhenEmpty: true, getLabel: (): string => i18n.t('modelDetail.cards.metrics.last_used') }
]);

const EXTERNAL_PROVIDER_ROWS: readonly RowDefinition[] = Object.freeze([
    { id: 'modeldetail-provider-api-url', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.api_url') },
    { id: 'modeldetail-provider-id', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.providerId') },
    { id: 'modeldetail-provider-created', copyable: true, getLabel: (): string => i18n.t('modelDetail.cards.externalProvider.created') }
]);

const SUPPRESSIBLE_SUMMARY_IDS: ReadonlySet<string> = new Set(SUMMARY_ROWS.filter((row) => row.suppressWhenEmpty === true).map((row) => row.id));

export { DETAIL_ROWS, EXTERNAL_PROVIDER_ROWS, STATUS_ROWS, SUMMARY_ROWS, SUPPRESSIBLE_SUMMARY_IDS };

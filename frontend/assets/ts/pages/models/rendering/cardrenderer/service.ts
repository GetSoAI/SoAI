/* SoAI - Models page card renderer service [frontend/assets/ts/pages/models/rendering/cardrenderer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderRecentItemBadge } from '@core/collectionpage/recentItemTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { capitalize } from '@core/primitives/text.ts';
import { isArray, isBoolean, isString } from '@core/typeGuards.ts';
import type { ModelData, ModelRecord } from '@core/types/modelTypes.ts';
import { renderAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { MODELS_ACTION_METRIC_BADGE } from '@core/models/pageActions.ts';
import type { CardData, MetricsBuildResult, ModelCardHost } from '@pages/models/rendering/cardrenderer/types.ts';

interface MetricItem {
    key: string;
    label: string;
    value: string | number;
    compactValue?: string | undefined;
    type: string;
    clickable: boolean;
}

interface MetricDisplayValue {
    fullValue: string;
    compactValue: string;
}

interface ModelStatusPresentation {
    badgeClass: string;
    label: string;
    statusClass: string;
}

interface ModelStatusPresentationHost {
    status: Pick<ModelCardHost['status'], 'getModelStatus' | 'presenter' | 'isExternalProviderModel'>;
}

const prepareCardData = (model: ModelData, host: ModelCardHost): CardData => {
    const cardId = host.identity.getItemCardId(model);
    const status = host.status.getModelStatus(model);
    const statusPresentation = resolveModelStatusPresentation(model, host);
    return {
        cardId,
        status,
        statusClass: statusPresentation.statusClass,
        statusBadgeClass: statusPresentation.badgeClass,
        statusLabel: statusPresentation.label,
        pluginName: host.identity.getModelPlugin(model),
        providerName: host.identity.getModelProvider(model),
        baseIdentifier: host.identity.getModelOriginId(model)
    };
};

const isModelDisabled = (model: ModelData, status: string | null): boolean => (isBoolean(model.isEnabled) && model.isEnabled === false) || (model.type !== 'virtual' && status === 'DISABLED');

const isModelNew = (model: ModelRecord, host: ModelCardHost): boolean => model.isOrphaned !== true && host.status.isNewItem(model);

const resolveModelStatusPresentation = (model: ModelRecord, host: ModelStatusPresentationHost): ModelStatusPresentation => {
    const status = host.status.getModelStatus(model);
    let badgeClass = status ? host.status.presenter.getCollectionBadgeClass(status) : '';
    let label = status ? host.status.presenter.getDescription(status) : '';
    const statusClass = status ? host.status.presenter.getCollectionStatusClass(status) : '';
    if (model.type === 'virtual') {
        if (model.isEnabled === false) {
            return {
                badgeClass: host.status.presenter.getCollectionBadgeClass('DISABLED'),
                label: host.status.presenter.getDescription('DISABLED'),
                statusClass: host.status.presenter.getCollectionStatusClass('DISABLED')
            };
        }
        return {
            badgeClass: 'status-persistentgreen',
            label: i18n.t('models.status.available'),
            statusClass: host.status.presenter.getCollectionStatusClass('PERSISTENT_READY')
        };
    }
    if (status === 'DISABLED') {
        return {
            badgeClass: host.status.presenter.getCollectionBadgeClass(status),
            label: host.status.presenter.getDescription(status),
            statusClass: host.status.presenter.getCollectionStatusClass(status)
        };
    }
    if (host.status.isExternalProviderModel(model)) {
        const normalizedStatus = host.status.presenter.normalizeStatus(model.pluginStatus);
        if (normalizedStatus === 'PROCESSING') {
            return {
                badgeClass: host.status.presenter.getCollectionBadgeClass(normalizedStatus),
                label: i18n.t('models.status.processing'),
                statusClass: host.status.presenter.getCollectionStatusClass(normalizedStatus)
            };
        }
        return {
            badgeClass: 'status-persistentgreen',
            label: i18n.t('models.status.available'),
            statusClass: host.status.presenter.getCollectionStatusClass('PERSISTENT_READY')
        };
    }
    if (status === 'STOPPED') {
        label = i18n.t('models.status.unloaded');
    }
    return {
        badgeClass,
        label,
        statusClass
    };
};

const formatModelTokenCount = (model: ModelData, host: ModelCardHost): MetricDisplayValue => {
    const tokens = host.metrics.resolveModelTokenCount(model);
    return {
        fullValue: host.metrics.formatNumber(tokens),
        compactValue: formatCompactNumber(tokens)
    };
};

const buildBadges = (model: ModelData, host: ModelCardHost): string => {
    const badges: string[] = [];
    if (isModelNew(model, host)) {
        badges.push(renderRecentItemBadge((value) => host.presentation.sanitizeText(value)));
    }
    if (model.hasAlias) {
        badges.push(`<span class="alias-badge">${i18n.t('models.badges.alias')}</span>`);
    }
    if (model.isOrphaned) {
        badges.push(`<span class="orphan-badge">${i18n.t('models.badges.orphaned')}</span>`);
    }
    return badges.join('');
};

const buildModelTypeBadge = (model: ModelData, host: ModelCardHost): string => {
    const rawType = isString(model?.modelType) ? model.modelType.trim() : '';
    if (!rawType) {
        return '';
    }
    const badgeClass = getBadgeColorClass(rawType);
    const label = host.presentation.sanitizeText(rawType.toUpperCase());
    return `<div class="ui-model-type-badges ui-model-type-badges--inline"><span class="ui-model-type-badge ${badgeClass}">${label}</span></div>`;
};

const buildMetrics = (model: ModelData, providerName: string, host: ModelCardHost): MetricsBuildResult => {
    const isExternal = host.status.isExternalProviderModel(model);
    const typeLabel = model.type === 'local' ? i18n.t('models.types.local') : capitalize(model.type || i18n.t('models.types.unknown'));
    const rawRequestCount = host.metrics.resolveModelRequestCount(model);
    const requestCount = host.metrics.formatNumber(rawRequestCount);
    const commonMetrics: MetricItem[] = [
        {
            key: 'PARAMETERS',
            label: i18n.t('models.metrics.parameters'),
            value: model.modelHasCustomParameters ? i18n.t('models.metrics.custom') : i18n.t('models.metrics.default'),
            type: 'secondary',
            clickable: true
        },
        {
            key: 'REQUESTS',
            label: i18n.t('models.metrics.requests'),
            value: requestCount,
            type: 'tertiary',
            clickable: true
        },
        {
            key: 'TYPE',
            label: i18n.t('models.metrics.type'),
            value: typeLabel,
            type: 'quaternary',
            clickable: false
        }
    ];

    let metrics: MetricItem[] = [];
    const statusPresentation = resolveModelStatusPresentation(model, host);
    const statusBadgeClass = statusPresentation.badgeClass;
    const statusLabel = statusPresentation.label;
    let resolvedProviderLabel = providerName;

    if (model.type === 'virtual') {
        const count = isArray(model.models) ? model.models.length : model.constituents || 0;
        const strategy = host.metrics.formatStrategyLabel(model.strategy);
        metrics = [
            {
                key: 'TYPE',
                label: i18n.t('models.metrics.type'),
                value: i18n.t('models.types.virtual'),
                type: 'primary',
                clickable: false
            },
            {
                key: 'STRATEGY',
                label: i18n.t('models.metrics.strategy'),
                value: strategy,
                type: 'secondary',
                clickable: false
            },
            {
                key: 'CONSTITUENT_MODELS',
                label: i18n.t('models.metrics.constituentModelsShort'),
                value: count || 0,
                type: 'tertiary',
                clickable: false
            },
            {
                key: 'REQUESTS',
                label: i18n.t('models.metrics.requests'),
                value: requestCount,
                type: 'quaternary',
                clickable: false
            }
        ];
        resolvedProviderLabel = '';
    } else if (isExternal) {
        const truncatedProvider = providerName.length > 20 ? `${providerName.slice(0, 17)}...` : providerName;
        const tokenMetric = formatModelTokenCount(model, host);
        resolvedProviderLabel = truncatedProvider;
        metrics = [
            {
                key: 'TOKENS',
                label: i18n.t('models.metrics.tokens'),
                value: tokenMetric.fullValue,
                compactValue: tokenMetric.compactValue,
                type: 'primary',
                clickable: true
            },
            ...commonMetrics
        ];
    } else {
        metrics = [
            {
                key: 'MODEL_SIZE',
                label: i18n.t('models.metrics.modelSize'),
                value: formatBytes(model.sizeBytes),
                type: 'primary',
                clickable: true
            },
            ...commonMetrics
        ];
    }

    const metricsMarkup = metrics
        .map((metric) => {
            const label = host.presentation.sanitizeText(metric.label);
            const sanitizedValue = host.presentation.sanitizeText(String(metric.value ?? ''));
            const attr = metric.key ? host.sanitizeClassName(metric.key, 'metric') : '';
            const actionAttr = metric.clickable ? ` data-action="${MODELS_ACTION_METRIC_BADGE}"` : '';
            const keyAttr = attr ? ` data-metric-key="${attr}"` : '';
            const value = metric.compactValue ? renderAdaptiveNumber(String(metric.value), metric.compactValue) : sanitizedValue;
            return `<div class="ui-metric-item"><div class="ui-metric-badge ui-metric-badge--${metric.type}"${actionAttr}${keyAttr}><span class="ui-metric-label">${label}</span><span class="ui-metric-value">${value}</span></div></div>`;
        })
        .join('');

    return {
        metricsMarkup,
        statusBadgeClass: statusBadgeClass ?? '',
        statusLabel: statusLabel ?? '',
        providerLabel: resolvedProviderLabel
    };
};

export { buildBadges, buildMetrics, buildModelTypeBadge, isModelDisabled, isModelNew, prepareCardData, resolveModelStatusPresentation };
export type { ModelStatusPresentation, ModelStatusPresentationHost };

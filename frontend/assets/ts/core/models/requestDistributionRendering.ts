/* SoAI - Shared models request distribution rendering [frontend/assets/ts/core/models/requestDistributionRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { type RequestDistributionEntry, type RequestDistributionSource } from '@core/models/requestDistribution.ts';
import { toSurfaceColor } from '@core/models/requestDistributionColors.ts';
import { REQUEST_DISTRIBUTION_CHART_KINDS, type RequestDistributionChartKind } from '@core/models/requestDistributionKind.ts';
import { formatPercentFromFraction } from '@core/primitives/percent.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { CHART_COLOR_COUNT } from '@core/ui/chartColors.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

interface RequestDistributionLegendItem {
    label: string;
    detail: string;
    swatchIndex: number;
    swatchColor: string;
    swatchStyle: string;
}

interface RequestDistributionViewState {
    getChartKind: () => RequestDistributionChartKind;
    getSource: () => RequestDistributionSource;
    getNextSource: () => RequestDistributionSource;
    toggleSource: () => RequestDistributionSource;
    attachChartKindCycle: (element: HTMLElement, onCycle: () => void, options?: RequestDistributionChartKindCycleOptions) => void;
}

interface RequestDistributionStorage {
    get: (key: string, defaultValue?: JsonValue | null | undefined) => JsonValue | null | undefined;
    set: (key: string, value: JsonValue | null | undefined) => void;
}

interface RequestDistributionViewStateOptions {
    includeApiKeys?: boolean;
    storage?: RequestDistributionStorage;
    storageKey?: string;
}

interface RequestDistributionChartKindCycleOptions {
    shouldCycle?: () => boolean;
}

interface RequestDistributionChartKindCycleBinding {
    onCycle: () => void;
    options: RequestDistributionChartKindCycleOptions;
}

const STANDARD_REQUEST_DISTRIBUTION_SOURCES: readonly RequestDistributionSource[] = ['model', 'plugin', 'token'];
const ADMIN_REQUEST_DISTRIBUTION_SOURCES: readonly RequestDistributionSource[] = ['model', 'plugin', 'apiKey', 'token'];
const DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY = 'dashboard_request_distribution_source';
const METRICS_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY = 'metrics_request_distribution_source';

const resolveNextChartKind = (current: RequestDistributionChartKind): RequestDistributionChartKind => {
    const currentIndex = REQUEST_DISTRIBUTION_CHART_KINDS.indexOf(current);
    const nextIndex = (currentIndex + 1) % REQUEST_DISTRIBUTION_CHART_KINDS.length;
    const next = REQUEST_DISTRIBUTION_CHART_KINDS[nextIndex];
    if (!next) {
        throw new Error('Request distribution chart cycle list is empty');
    }
    return next;
};

const resolveNextSource = (sources: readonly RequestDistributionSource[], current: RequestDistributionSource): RequestDistributionSource => {
    const sourceIndex = sources.indexOf(current);
    return sources[(sourceIndex + 1) % sources.length] ?? 'model';
};

const isRequestDistributionSource = (value: JsonValue | null | undefined): value is RequestDistributionSource => value === 'model' || value === 'plugin' || value === 'apiKey' || value === 'token';

const readStoredRequestDistributionSource = (storage: RequestDistributionStorage | undefined, storageKey: string | undefined, sources: readonly RequestDistributionSource[]): RequestDistributionSource => {
    if (!storage || !storageKey) {
        return 'model';
    }
    try {
        const stored = storage.get(storageKey, 'model');
        return isRequestDistributionSource(stored) && sources.includes(stored) ? stored : 'model';
    } catch (error) {
        errorHandler.warn('RequestDistribution', 'Failed to read persisted source', ensureError(error));
        return 'model';
    }
};

const writeStoredRequestDistributionSource = (storage: RequestDistributionStorage | undefined, storageKey: string | undefined, source: RequestDistributionSource): void => {
    if (!storage || !storageKey) {
        return;
    }
    try {
        storage.set(storageKey, source);
    } catch (error) {
        errorHandler.warn('RequestDistribution', 'Failed to persist source', ensureError(error));
    }
};

const createRequestDistributionViewState = (options: RequestDistributionViewStateOptions = {}): RequestDistributionViewState => {
    let chartKind: RequestDistributionChartKind = 'pie3d';
    const sources = options.includeApiKeys === true ? ADMIN_REQUEST_DISTRIBUTION_SOURCES : STANDARD_REQUEST_DISTRIBUTION_SOURCES;
    const storageKey = options.storageKey?.trim() ? options.storageKey.trim() : undefined;
    let source: RequestDistributionSource = readStoredRequestDistributionSource(options.storage, storageKey, sources);
    const attachedElements = new WeakMap<HTMLElement, RequestDistributionChartKindCycleBinding>();
    return {
        getChartKind: (): RequestDistributionChartKind => chartKind,
        getSource: (): RequestDistributionSource => source,
        getNextSource: (): RequestDistributionSource => resolveNextSource(sources, source),
        toggleSource: (): RequestDistributionSource => {
            source = resolveNextSource(sources, source);
            writeStoredRequestDistributionSource(options.storage, storageKey, source);
            return source;
        },
        attachChartKindCycle: (element: HTMLElement, onCycle: () => void, cycleOptions: RequestDistributionChartKindCycleOptions = {}): void => {
            setTooltipText(element, resolveRequestDistributionChartToggleLabel());
            const existingBinding = attachedElements.get(element);
            if (existingBinding) {
                existingBinding.onCycle = onCycle;
                existingBinding.options = cycleOptions;
                return;
            }
            const binding: RequestDistributionChartKindCycleBinding = {
                onCycle,
                options: cycleOptions
            };
            attachedElements.set(element, binding);
            element.addEventListener('click', (event: MouseEvent): void => {
                if (binding.options.shouldCycle?.() === false) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                chartKind = resolveNextChartKind(chartKind);
                binding.onCycle();
            });
        }
    };
};

const resolveRequestDistributionSourceToggleLabel = (targetSource: RequestDistributionSource): string => {
    if (targetSource === 'apiKey') {
        return i18n.t('metrics.cards.requestDistribution.actions.showApiKeys');
    }
    if (targetSource === 'plugin') {
        return i18n.t('metrics.cards.requestDistribution.actions.showPlugins');
    }
    if (targetSource === 'token') {
        return i18n.t('metrics.cards.requestDistribution.actions.showTokens');
    }
    return i18n.t('metrics.cards.requestDistribution.actions.showModels');
};

const resolveRequestDistributionTitle = (source: RequestDistributionSource): string => {
    if (source === 'plugin') {
        return i18n.t('metrics.cards.requestDistribution.titles.plugins');
    }
    if (source === 'apiKey') {
        return i18n.t('metrics.cards.requestDistribution.titles.apiKeys');
    }
    if (source === 'token') {
        return i18n.t('metrics.cards.requestDistribution.titles.tokens');
    }
    return i18n.t('metrics.cards.requestDistribution.titles.models');
};

const resolveRequestDistributionChartToggleLabel = (): string => i18n.t('metrics.cards.requestDistribution.actions.toggleChartType');
const resolveRequestDistributionEmptyStateText = (): string => i18n.t('metrics.cards.requestDistribution.emptyState');

const resolveRequestDistributionPalette = (resolveColor: (token: string) => string | null | undefined): string[] => {
    const colors: string[] = [];
    for (let index = 0; index < CHART_COLOR_COUNT; index += 1) {
        const color = resolveColor(`--chart-color-${String(index)}`);
        if (typeof color === 'string' && color) {
            colors.push(color);
        }
    }
    return colors;
};

const resolveLegendSwatchColor = (colors: readonly string[], swatchIndex: number): string => {
    const resolved = colors[swatchIndex % colors.length];
    return colors.length > 0 && resolved ? toSurfaceColor(resolved) : `var(--chart-color-${String(swatchIndex)})`;
};

const buildRequestDistributionLegendItems = (entries: readonly RequestDistributionEntry[], formatValue: (value: number) => string, colors: readonly string[]): RequestDistributionLegendItem[] => {
    return entries.map((entry) => {
        const formattedValue = formatValue(entry.value);
        const swatchColor = resolveLegendSwatchColor(colors, entry.swatchIndex);
        return {
            label: entry.label,
            detail: `${formattedValue} • ${formatPercentFromFraction(entry.ratio)}`,
            swatchIndex: entry.swatchIndex,
            swatchColor,
            swatchStyle: `--distribution-legend-swatch-color: ${swatchColor};`
        };
    });
};

export { DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY, METRICS_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY, buildRequestDistributionLegendItems, createRequestDistributionViewState, resolveRequestDistributionChartToggleLabel, resolveRequestDistributionEmptyStateText, resolveRequestDistributionPalette, resolveRequestDistributionSourceToggleLabel, resolveRequestDistributionTitle };
export type { RequestDistributionChartKind, RequestDistributionLegendItem, RequestDistributionStorage, RequestDistributionViewState };

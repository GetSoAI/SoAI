/* SoAI - System metrics V1 metadata contracts [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsMetadataContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { decodeBooleanFields, decodeFiniteNumberArray, decodeFiniteNumberFields, decodeStringArray, decodeStringFields, optionalMetricsObject } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';

interface MetricsHistoryConfiguration extends JsonObject {
    enabled?: boolean;
    retentionHours?: number;
    loggingIntervalMs?: number;
    maxPoints?: number;
    defaultIntervalMs?: number;
    supportsOhlc?: boolean;
    supportedIntervalsMs?: number[];
    supportedAggregations?: string[];
}
interface MetricsCatalogEntry extends JsonObject {
    type?: string;
    unit?: string;
    aggregations?: string[];
}
interface MetricsCapabilities extends JsonObject {
    historyConfiguration?: MetricsHistoryConfiguration;
    metricsCatalog?: Record<string, MetricsCatalogEntry>;
}

const decodeMetricsCapabilities = (root: JsonObject): MetricsCapabilities | undefined => {
    const source = optionalMetricsObject(root, 'capabilities', 'system.metrics');
    if (!source) return undefined;
    const decoded: MetricsCapabilities = {};
    const historyConfiguration = optionalMetricsObject(source, 'history_config', 'system.metrics.capabilities');
    if (historyConfiguration) {
        const configuration: MetricsHistoryConfiguration = {
            ...decodeFiniteNumberFields(historyConfiguration, { 'retention_hours': 'retentionHours', 'logging_interval_ms': 'loggingIntervalMs', 'max_points': 'maxPoints', 'default_interval_ms': 'defaultIntervalMs' }, 'system.metrics.capabilities.history_config'),
            ...decodeBooleanFields(historyConfiguration, { enabled: 'enabled', 'supports_ohlc': 'supportsOhlc' }, 'system.metrics.capabilities.history_config')
        };
        const supportedIntervals = historyConfiguration['supported_intervals_ms'];
        const supportedAggregations = historyConfiguration['supported_aggregations'];
        if (supportedIntervals !== undefined && supportedIntervals !== null) configuration.supportedIntervalsMs = decodeFiniteNumberArray(supportedIntervals, 'system.metrics.capabilities.history_config.supported_intervals_ms');
        if (supportedAggregations !== undefined && supportedAggregations !== null) configuration.supportedAggregations = decodeStringArray(supportedAggregations, 'system.metrics.capabilities.history_config.supported_aggregations');
        decoded.historyConfiguration = configuration;
    }
    const catalog = optionalMetricsObject(source, 'metrics_catalog', 'system.metrics.capabilities');
    if (catalog) {
        const decodedCatalog: Record<string, MetricsCatalogEntry> = {};
        for (const [metricPath, value] of Object.entries(catalog)) {
            if (!isJsonObject(value)) throw new TypeError(`system.metrics.capabilities.metrics_catalog.${metricPath} must be an object`);
            const entry = decodeStringFields(value, { type: 'type', unit: 'unit' }, `system.metrics.capabilities.metrics_catalog.${metricPath}`);
            const aggregations = value['aggregations'];
            if (aggregations !== undefined && aggregations !== null) entry['aggregations'] = decodeStringArray(aggregations, `system.metrics.capabilities.metrics_catalog.${metricPath}.aggregations`);
            decodedCatalog[metricPath] = entry;
        }
        decoded.metricsCatalog = decodedCatalog;
    }
    return decoded;
};

const decodeMetricsCapabilitiesSnapshot = (value: JsonValue): MetricsCapabilities => {
    const source = requireRecord(value, 'system.metrics.capabilities snapshot');
    const decoded = decodeMetricsCapabilities({ capabilities: source });
    if (!decoded || (!decoded.historyConfiguration && !decoded.metricsCatalog)) throw new TypeError('system.metrics.capabilities snapshot returned empty payload');
    return decoded;
};

const decodeTokenRates = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'token_rates', 'system.metrics');
    if (!source) return undefined;
    const total = requireRecord(source['total'], 'system.metrics.token_rates.total');
    const plugins = requireRecord(source['plugins'], 'system.metrics.token_rates.plugins');
    const decodedPlugins: JsonObject = {};
    for (const [pluginName, value] of Object.entries(plugins)) {
        if (!isJsonObject(value)) throw new TypeError(`system.metrics.token_rates.${pluginName} must be an object`);
        decodedPlugins[pluginName] = decodeFiniteNumberFields(value, { 'effective_rate': 'effectiveRate', 'delivered_rate_5s': 'deliveredRate5s', 'delivered_rate_30s': 'deliveredRate30s', 'active_streams': 'activeStreams' }, `system.metrics.token_rates.plugins.${pluginName}`);
    }
    return {
        total: decodeFiniteNumberFields(total, { 'effective_rate': 'effectiveRate', 'delivered_rate_5s': 'deliveredRate5s', 'delivered_rate_30s': 'deliveredRate30s', 'active_streams': 'activeStreams' }, 'system.metrics.token_rates.total'),
        plugins: decodedPlugins
    };
};

export { decodeMetricsCapabilities, decodeMetricsCapabilitiesSnapshot, decodeTokenRates };
export type { MetricsCapabilities, MetricsCatalogEntry, MetricsHistoryConfiguration };

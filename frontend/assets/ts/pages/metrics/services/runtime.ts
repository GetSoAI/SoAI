/* SoAI - Metrics page runtime [frontend/assets/ts/pages/metrics/services/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { METRICS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { readPayloadPathValue } from '@core/types/payloadPathReader.ts';
import { FrontendTelemetryPresenter, MetricsFormatter, type FrontendTelemetryHost, type MetricsKpiHost, type TelemetryService } from '@features/metrics/public.ts';
import { metricsLogger } from '@pages/metrics/contracts/MetricsPageSupport.ts';
import { loadMetricsCapabilities } from '@pages/metrics/controllers/page/capabilities.ts';
import type { MetricsRuntimeContext } from '@pages/metrics/controllers/page/contracts.ts';
import { initializeMetricsFrontendTelemetryCard, initializeMetricsMainChart, reloadMetricsChartData, syncMetricsChartControls } from '@pages/metrics/controllers/page/effects.ts';
import { processMetricsUpdate } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { initializeMetricsStream } from '@pages/metrics/realtime/metricsPageRealtime.ts';
import type { MetricsData } from '@pages/metrics/types.ts';
import { updateApiKeyUsageFromSnapshot } from '@pages/metrics/widgets/apiKeyUsageTableWidget.ts';
import { updatePluginHealth } from '@pages/metrics/widgets/service.ts';

interface MetricsPageServicesHost {
    owners: PageUiOwnerHost & { pageContext: PageContext | null };
}

type MetricsDeferredHost = MetricsRuntimeContext;

interface MetricsPageServices {
    metricsFormatter: MetricsFormatter;
    telemetry: TelemetryService | null;
    telemetryPresenter: FrontendTelemetryPresenter | null;
    kpiHost: MetricsKpiHost;
}

const resolveNumberFromPath = <T>(root: T, path: readonly string[]): number => {
    return readRuntimeFiniteNumberOrFallbackValue(readPayloadPathValue(root, path), Number.NaN);
};

const isTelemetryService = <T>(value: T): value is T & TelemetryService => {
    return isObject(value) && (hasFunctionProperty(value, 'getMetric') || hasFunctionProperty(value, 'observeMetric') || hasFunctionProperty(value, 'subscribe') || hasFunctionProperty(value, 'getStatus'));
};

const resolveMetricsTelemetryService = (host: MetricsPageServicesHost): TelemetryService | null => {
    const telemetryValue = host.owners.pageContext?.telemetry ?? null;
    if (telemetryValue === null) {
        return null;
    }
    if (!isTelemetryService(telemetryValue)) {
        throw new Error('Telemetry service present but missing expected API surface');
    }
    return telemetryValue;
};

const createMetricsTelemetryHost = (host: MetricsPageServicesHost): FrontendTelemetryHost => ({
    setUIValue: (id: string, value: string | null | undefined, options?: { allowNull?: boolean }): void => {
        host.owners.pageElements.setValue(id, value, options);
    }
});

const createMetricsKpiHost = (host: { metricsFormatter: MetricsFormatter }): MetricsKpiHost =>
    Object.freeze({
        metricsFormatter: host.metricsFormatter,
        calculateTotalRequests: (metrics: MetricsData): number => resolveNumberFromPath(metrics, ['director', 'requests', 'completed']),
        calculateAverageLatency: (metrics: MetricsData): number => {
            const latencyMs = resolveNumberFromPath(metrics, ['director', 'gauges', 'requestLatencyMs']);
            return latencyMs > 0 ? latencyMs : Number.NaN;
        }
    });

const createMetricsPageServices = (host: MetricsPageServicesHost): MetricsPageServices => {
    const metricsFormatter = new MetricsFormatter({ formatting: { formatRelativeTime: (timestamp) => formatRelativeTime(timestamp, serverEpochMs()) } });
    const telemetry = resolveMetricsTelemetryService(host);
    const telemetryPresenter = telemetry
        ? new FrontendTelemetryPresenter({
              host: createMetricsTelemetryHost(host),
              telemetry,
              formatter: metricsFormatter,
              logger: metricsLogger
          })
        : null;
    const kpiHost = createMetricsKpiHost({ metricsFormatter });
    return { metricsFormatter, telemetry, telemetryPresenter, kpiHost };
};

class MetricsDeferredController {
    #deferredInitializePromise: Promise<void> | null = null;
    #deferredInitializeSignal: AbortSignal | null = null;
    #metricsDisposer: (() => void) | null = null;
    #pluginsDisposer: (() => void) | null = null;
    #apiKeyUsageTimer: number | null = null;
    #apiKeyUsageRequestInFlight = false;
    #lifecycleSequence = 0;
    readonly host: MetricsDeferredHost;

    constructor(host: MetricsDeferredHost) {
        this.host = host;
    }

    async prepare(signal: AbortSignal): Promise<void> {
        if (this.#deferredInitializePromise) {
            if (this.#deferredInitializeSignal?.aborted === true) {
                this.#deferredInitializePromise = null;
                this.#deferredInitializeSignal = null;
            } else {
                return this.#deferredInitializePromise;
            }
        }
        if (signal.aborted) {
            return;
        }
        const promise = this.#prepare(signal);
        this.#deferredInitializeSignal = signal;
        const trackedPromise = promise.finally(() => {
            if (this.#deferredInitializePromise === trackedPromise) {
                this.#deferredInitializePromise = null;
                this.#deferredInitializeSignal = null;
            }
        });
        this.#deferredInitializePromise = trackedPromise;
        return this.#deferredInitializePromise;
    }

    async start(signal: AbortSignal, lifecycleSequence: number): Promise<void> {
        await this.#initializeMetricsStream(signal, lifecycleSequence);
    }

    hide(): void {
        this.#lifecycleSequence += 1;
        this.disposeMetricsSubscription();
        this.disposePluginsSubscription();
        this.#clearApiKeyUsageTimer();
        this.#deferredInitializePromise = null;
        this.#deferredInitializeSignal = null;
    }

    disposeMetricsSubscription(): void {
        const disposer = this.#metricsDisposer;
        if (!disposer) {
            return;
        }
        this.#metricsDisposer = null;
        this.host.owners.pageResources.untrack(disposer);
        disposer();
    }

    disposePluginsSubscription(): void {
        const disposer = this.#pluginsDisposer;
        if (!disposer) {
            return;
        }
        this.#pluginsDisposer = null;
        this.host.owners.pageResources.untrack(disposer);
        disposer();
    }

    async #prepare(signal: AbortSignal): Promise<void> {
        await this.start(signal, this.#lifecycleSequence);
        if (signal.aborted) {
            return;
        }
        await loadMetricsCapabilities(this.host, signal);
        if (signal.aborted) {
            return;
        }
        await syncMetricsChartControls(this.host);
        if (signal.aborted) {
            return;
        }
        if (!this.host.state.mainChart) {
            await initializeMetricsMainChart(this.host, signal);
        }
        if (signal.aborted) {
            return;
        }
        await reloadMetricsChartData(this.host, true);
        if (signal.aborted) {
            return;
        }
        await initializeMetricsFrontendTelemetryCard(this.host);
        if (signal.aborted) {
            return;
        }
        this.#scheduleApiKeyUsagePoll(0, this.#lifecycleSequence, signal);
    }

    #clearApiKeyUsageTimer(): void {
        this.host.owners.pageResources.clearTimer(this.#apiKeyUsageTimer);
        this.#apiKeyUsageTimer = null;
    }

    #scheduleApiKeyUsagePoll(delayMs: number, lifecycleSequence: number, signal: AbortSignal): void {
        if (!this.host.owners.auth.isAdmin() || signal.aborted || lifecycleSequence !== this.#lifecycleSequence) {
            return;
        }
        this.#clearApiKeyUsageTimer();
        this.#apiKeyUsageTimer = this.host.owners.pageResources.setTimer(() => {
            terminateHandledPromise(this.#pollApiKeyUsage(lifecycleSequence, signal));
        }, delayMs);
    }

    async #pollApiKeyUsage(lifecycleSequence: number, signal: AbortSignal): Promise<void> {
        if (signal.aborted || lifecycleSequence !== this.#lifecycleSequence || !this.host.owners.auth.isAdmin()) {
            return;
        }
        if (this.#apiKeyUsageRequestInFlight) {
            this.#scheduleApiKeyUsagePoll(2000, lifecycleSequence, signal);
            return;
        }
        this.#apiKeyUsageRequestInFlight = true;
        let nextDelayMs = 2000;
        try {
            const snapshot = await requestWebSocketSnapshotPayload('openai_api_keys.usage');
            if (!signal.aborted && lifecycleSequence === this.#lifecycleSequence) {
                updateApiKeyUsageFromSnapshot(this.host, snapshot);
            }
        } catch (error) {
            nextDelayMs = 10000;
            this.host.operations.logger('debug', 'API key usage metrics snapshot failed', ensureError(error));
        } finally {
            this.#apiKeyUsageRequestInFlight = false;
            this.#scheduleApiKeyUsagePoll(nextDelayMs, lifecycleSequence, signal);
        }
    }

    async #initializeMetricsStream(signal: AbortSignal, lifecycleSequence: number): Promise<void> {
        await initializeMetricsStream(
            {
                subscribeToData: (resource: string, handler: (value: JsonValue | null) => void) => this.host.owners.streaming.subscribeResourceValue(resource, handler),
                ensureDataSubscriptions: (options) => this.host.owners.streaming.ensureSubscriptions(options),
                pageResources: this.host.owners.pageResources,
                requestAnimationFrame: (callback) => this.host.operations.requestAnimationFrame(callback),
                cancelAnimationFrame: (frameId) => this.host.operations.cancelAnimationFrame(frameId),
                isActive: () => this.#lifecycleSequence === lifecycleSequence && !signal.aborted,
                processMetricsUpdate: (data: MetricsData) => processMetricsUpdate(this.host, data),
                processPluginsUpdate: (data: readonly JsonValue[]) => {
                    this.host.state.currentPlugins = data;
                    updatePluginHealth(this.host);
                },
                setMetricsDisposer: (disposer: (() => void) | null) => {
                    this.#metricsDisposer = disposer;
                },
                setPluginsDisposer: (disposer: (() => void) | null) => {
                    this.#pluginsDisposer = disposer;
                },
                disposeMetricsSubscription: () => this.disposeMetricsSubscription(),
                disposePluginsSubscription: () => this.disposePluginsSubscription(),
                metricsStreamId: METRICS,
                pluginsStreamId: PLUGINS
            },
            signal
        );
    }
}

export { createMetricsPageServices, MetricsDeferredController };

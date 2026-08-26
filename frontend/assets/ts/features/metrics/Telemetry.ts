/* SoAI - Metrics feature telemetry [frontend/assets/ts/features/metrics/Telemetry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogLevel } from '@core/moduleContext.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { WEBSOCKET_LATENCY_METRIC_NAME } from '@core/websocketclient/constants.ts';
import type { MetricsFormatter } from '@features/metrics/Formatter.ts';
import { buildFrontendTelemetryCardValues, type TelemetryEvent, type TelemetryMetric, type TelemetryStatus } from '@features/metrics/telemetryCardValues.ts';
interface FrontendTelemetryState {
    connection: TelemetryMetric | null;
    latency: TelemetryMetric | null;
    queue: TelemetryMetric | null;
    lastEvent: TelemetryEvent | null;
    status: TelemetryStatus | null;
}
interface FrontendTelemetryHost {
    setUIValue: (id: string, value: string | null | undefined, options?: { allowNull?: boolean }) => void;
}
interface TelemetryService {
    getMetric?: (key: string) => TelemetryMetric | null;
    observeMetric?: (key: string, handler: (metric: TelemetryMetric | null) => void) => (() => void) | null;
    subscribe?: (handler: (event: TelemetryEvent | null) => void) => (() => void) | null;
    getStatus?: () => TelemetryStatus | null;
}
interface FrontendTelemetryPresenterOptions {
    host: FrontendTelemetryHost;
    telemetry: TelemetryService;
    formatter: MetricsFormatter;
    logger: (level: LogLevel, message: string, error?: Error) => void;
    onUpdate?: (() => void) | null;
}
type TelemetryDisposer = () => void;
const FRONTEND_TELEMETRY_DEFAULT: FrontendTelemetryState = Object.freeze({
    connection: null,
    latency: null,
    queue: null,
    lastEvent: null,
    status: null
});
class FrontendTelemetryPresenter {
    #host: FrontendTelemetryHost;
    #telemetry: TelemetryService;
    #formatter: MetricsFormatter;
    #logger: (level: LogLevel, message: string, error?: Error) => void;
    #onUpdate: (() => void) | null;
    #state: FrontendTelemetryState = { ...FRONTEND_TELEMETRY_DEFAULT };
    #initialized = false;
    #disposers: TelemetryDisposer[] = [];
    constructor({ host, telemetry, formatter, logger, onUpdate = null }: FrontendTelemetryPresenterOptions) {
        if (!host) {
            throw new Error('FrontendTelemetryPresenter requires a host instance');
        }
        if (!telemetry) {
            throw new Error('FrontendTelemetryPresenter requires a telemetry service');
        }
        if (!formatter) {
            throw new Error('FrontendTelemetryPresenter requires a formatter');
        }
        if (!isFunction(logger)) {
            throw new Error('FrontendTelemetryPresenter requires a logger function');
        }
        this.#onUpdate = isFunction(onUpdate) ? onUpdate : null;
        this.#host = host;
        this.#telemetry = telemetry;
        this.#formatter = formatter;
        this.#logger = logger;
    }
    async initialize(): Promise<void> {
        if (this.#initialized) {
            this.updateCard();
            return;
        }
        this.#initialized = true;
        if (isFunction(this.#telemetry?.getMetric)) {
            const connectionMetric = this.#telemetry.getMetric('connection.status');
            if (connectionMetric) {
                this.#state.connection = connectionMetric;
            }
            const latencyMetric = this.#telemetry.getMetric(WEBSOCKET_LATENCY_METRIC_NAME);
            if (latencyMetric) {
                this.#state.latency = latencyMetric;
            }
            const queueMetric = this.#telemetry.getMetric('stream.queueDepth');
            if (queueMetric) {
                this.#state.queue = queueMetric;
            }
        }
        this.refreshStatus();
        if (isFunction(this.#telemetry?.observeMetric)) {
            this.registerDisposer(
                this.#telemetry.observeMetric('connection.status', (metric: TelemetryMetric | null) => {
                    this.#state.connection = metric;
                    this.refreshStatus();
                    this.updateCard();
                })
            );
            this.registerDisposer(
                this.#telemetry.observeMetric(WEBSOCKET_LATENCY_METRIC_NAME, (metric: TelemetryMetric | null) => {
                    this.#state.latency = metric;
                    this.refreshStatus();
                    this.updateCard();
                })
            );
            this.registerDisposer(
                this.#telemetry.observeMetric('stream.queueDepth', (metric: TelemetryMetric | null) => {
                    this.#state.queue = metric;
                    this.refreshStatus();
                    this.updateCard();
                })
            );
        }
        if (isFunction(this.#telemetry?.subscribe)) {
            this.registerDisposer(
                this.#telemetry.subscribe((event: TelemetryEvent | null) => {
                    if (!event) {
                        return;
                    }
                    this.#state.lastEvent = event;
                    this.refreshStatus();
                    this.updateCard();
                })
            );
        }
        this.refreshStatus();
        this.updateCard();
    }
    refreshStatus(): TelemetryStatus | null {
        this.#state.status = isFunction(this.#telemetry?.getStatus) ? (this.#telemetry.getStatus() ?? null) : null;
        return this.#state.status;
    }
    updateCard(): void {
        const set = (id: string, value: JsonValue | null | undefined): void => this.#host.setUIValue(id, value === null || value === undefined ? value : String(value), { allowNull: true });
        const values = buildFrontendTelemetryCardValues({
            connection: this.#state.connection,
            latency: this.#state.latency,
            queue: this.#state.queue,
            lastEvent: this.#state.lastEvent,
            status: this.#state.status ?? this.refreshStatus(),
            formatter: this.#formatter
        });
        set('frontendConnectionValue', values.connection);
        set('frontendLatencyValue', values.latency);
        set('frontendStageValue', values.stage);
        set('frontendSubscribersValue', values.subscribers);
        set('frontendRestartSubscribersValue', values.restartSubscribers);
        set('frontendConnectionHoldsValue', values.connectionHolds);
        set('frontendQueueValue', values.queue);
        set('frontendThrottleValue', values.throttle);
        set('frontendPendingEventsValue', values.pendingEvents);
        set('frontendPendingMetricsValue', values.pendingMetrics);
        set('frontendSinksValue', values.sinks);
        set('frontendLastEventValue', values.lastEvent);
        set('frontendLastEventSeverityValue', values.lastEventSeverity);
        set('frontendLastEventModuleValue', values.lastEventModule);
        set('frontendStatusLabel', values.status);
        if (this.#onUpdate) {
            try {
                this.#onUpdate();
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#logger('debug', 'Telemetry onUpdate callback failed', runtimeError);
            }
        }
    }
    registerDisposer(disposer: TelemetryDisposer | null | undefined): void {
        if (isFunction(disposer)) {
            this.#disposers.push(disposer);
        }
    }
    dispose(): void {
        if (this.#disposers.length) {
            while (this.#disposers.length) {
                const disposer = this.#disposers.pop();
                try {
                    disposer?.();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    this.#logger('debug', 'Telemetry disposer failed', runtimeError);
                }
            }
        }
        this.#disposers = [];
        this.#state = { ...FRONTEND_TELEMETRY_DEFAULT };
        this.#initialized = false;
    }
}
const telemetryModule = { FrontendTelemetryPresenter, FRONTEND_TELEMETRY_DEFAULT };
export { FrontendTelemetryPresenter, FRONTEND_TELEMETRY_DEFAULT, telemetryModule };
export type { FrontendTelemetryHost, TelemetryService };

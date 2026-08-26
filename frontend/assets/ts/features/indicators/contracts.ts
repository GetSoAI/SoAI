/* SoAI - Indicators feature boundary contracts [frontend/assets/ts/features/indicators/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryFields, TelemetryValue } from '@core/telemetry/contracts.ts';

interface TelemetryMetric {
    value?: TelemetryValue;
}

interface TelemetryEvent {
    stage?: string | undefined;
    timestamp?: number | undefined;
}

interface BundleResource {
    pending?: boolean | undefined;
    status?: string | undefined;
}

interface BundleInfo {
    name?: string | undefined;
    resources?: BundleResource[] | undefined;
}

interface DiagnosticsSnapshot {
    queueDepth?: number | null | undefined;
    bundles?: BundleInfo[] | undefined;
}

interface StorageInterface {
    ready?: Promise<void> | undefined;
    getLiveStatusOverlayEnabled?: () => boolean;
    setLiveStatusOverlayEnabled?: (enabled: boolean) => void;
}

interface StreamManagerInterface {
    getDiagnostics: () => DiagnosticsSnapshot;
}

interface TelemetryServiceInterface {
    observeMetric: (name: string, callback: (metric: TelemetryMetric) => void) => (() => void) | undefined;
    subscribe: (callback: (event: TelemetryEvent) => void) => (() => void) | undefined;
    publishMetric: (name: string, value: TelemetryValue, metadata?: TelemetryFields) => void;
}

interface SetEnabledOptions {
    persist?: boolean | undefined;
}

interface LiveStatusOverlayNodes {
    container: HTMLElement;
    statusElement: HTMLElement;
    latencyElement: HTMLElement;
    queueElement: HTMLElement;
    eventElement: HTMLElement;
    bundleContainer: HTMLElement;
}

interface TelemetryMetricState {
    connection: TelemetryMetric | null;
    latency: TelemetryMetric | null;
    queue: TelemetryMetric | null;
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export type { BundleInfo, BundleResource, DiagnosticsSnapshot, LogLevel, SetEnabledOptions, StorageInterface, StreamManagerInterface, TelemetryEvent, TelemetryMetric, TelemetryMetricState, LiveStatusOverlayNodes, TelemetryServiceInterface };

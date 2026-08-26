/* SoAI - Indicators feature public contracts [frontend/assets/ts/features/indicators/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DiagnosticsSnapshot, LogLevel, StorageInterface, StreamManagerInterface, TelemetryEvent, TelemetryMetricState, TelemetryMetric, SetEnabledOptions, BundleInfo, TelemetryServiceInterface } from '@features/indicators/contracts.ts';

interface LiveStatusOverlaySettingChangedEventDetail {
    enabled: boolean;
}

type LiveStatusOverlaySettingChangeHandler = (event: Event) => void;

type LiveStatusOverlayErrorLevel = 'debug' | 'info' | 'warn' | 'error';

type LiveStatusOverlayErrorReporter = (message: string, error: Error, level?: LiveStatusOverlayErrorLevel) => void;

interface LiveStatusOverlayState {
    container: HTMLElement | null;
    statusElement: HTMLElement | null;
    latencyElement: HTMLElement | null;
    queueElement: HTMLElement | null;
    eventElement: HTMLElement | null;
    bundleContainer: HTMLElement | null;
    unsubscribers: Array<() => void>;
    metrics: TelemetryMetricState;
    lastEvent: TelemetryEvent | null;
    streamManager: StreamManagerInterface | null;
    refreshHandle: number | null;
    refreshTask: Promise<void> | null;
    refreshTaskGeneration: number;
    refreshRequested: boolean;
    lifecycleGeneration: number;
    destroyed: boolean;
    storage: StorageInterface | null;
    telemetry: TelemetryServiceInterface | null;
    enabled: boolean;
    position: LiveStatusOverlayPosition | null;
    dragState: LiveStatusOverlayDragState | null;
    active: boolean;
    settingListenerRegistered: boolean;
}

interface LiveStatusOverlayPosition {
    left: number;
    top: number;
}

interface LiveStatusOverlayDragState {
    pointerId: number;
    offsetX: number;
    offsetY: number;
    disposers: Array<() => void>;
}

export type { DiagnosticsSnapshot, BundleInfo, LogLevel, TelemetryEvent, TelemetryMetric, LiveStatusOverlayDragState, LiveStatusOverlayErrorLevel, LiveStatusOverlayErrorReporter, LiveStatusOverlayPosition, LiveStatusOverlayState, TelemetryMetricState, TelemetryServiceInterface, SetEnabledOptions, LiveStatusOverlaySettingChangeHandler, LiveStatusOverlaySettingChangedEventDetail, StorageInterface, StreamManagerInterface };

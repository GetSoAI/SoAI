/* SoAI - SoAI Bench history modal public contracts [frontend/assets/ts/features/hardware/modals/soaibenchhistory/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface SoAIBenchHistoryOpenRequest {
    deviceId: string;
    gpuIndex: string;
    gpuName: string;
}

interface SoAIBenchHistoryTelemetry {
    overallScore: number | null;
    aluGops: number | null;
    matrixGops: number | null;
    latencyScore: number | null;
    latencyUs: number | null;
    latencyDispatchesPerSecond: number | null;
    computeGops: number | null;
    memoryGbs: number | null;
    maxTemperatureCelsius: number | null;
    avgPowerWatts: number | null;
    maxPowerWatts: number | null;
}

interface SoAIBenchHistoryRun {
    runId: string;
    profile: string;
    benchmarkMode: string;
    status: string;
    startedAtMs: number | null;
    durationMs: number | null;
    telemetry: SoAIBenchHistoryTelemetry;
    leaderboardEligible: boolean;
    leaderboardRejectionReason: string | null;
    scoreVariancePercent: number | null;
    settingsSnapshotAvailable: boolean;
    failureReason: string | null;
    unsupportedReason: string | null;
    matchBasis: string | null;
    staleHardware: boolean;
    raw: JsonObject;
}

interface SoAIBenchHistoryDisplayRow {
    runId: string;
    columns: readonly string[];
}

interface SoAIBenchHistoryModalHost {
    modals: ModalPresenterApi;
    downloadHistoryCsv(deviceId: string): Promise<Response>;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    setHTML(target: Element, html: TrustedHtml): void;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void>;
    addClassName(target: Element, className: string): void;
    removeClassName(target: Element, className: string): void;
    updateText(target: Element, text: string): void;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    getIconSync(iconName: IconName, options?: IconOptions): TrustedHtml;
}

interface SoAIBenchHistoryModalDependencies {
    host: SoAIBenchHistoryModalHost;
}

export type { SoAIBenchHistoryDisplayRow, SoAIBenchHistoryModalDependencies, SoAIBenchHistoryModalHost, SoAIBenchHistoryOpenRequest, SoAIBenchHistoryRun, SoAIBenchHistoryTelemetry };

/* SoAI - SoAI Bench run modal public contracts [frontend/assets/ts/features/hardware/modals/soaibenchrun/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationProgressReporter } from '@core/operationprogress/types.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface SoAIBenchRunOpenRequest {
    deviceId: string;
    gpuIndex: string;
    gpuName: string;
}

interface SoAIBenchRunMetrics {
    overallScore: number | null;
    computeScore: number | null;
    computeGops: number | null;
    aluGops: number | null;
    matrixGops: number | null;
    memoryScore: number | null;
    memoryGbs: number | null;
    latencyScore: number | null;
    latencyUs: number | null;
    latencyDispatchesPerSecond: number | null;
    coreUtilizationPercent: number | null;
    maxTemperatureCelsius: number | null;
    avgPowerWatts: number | null;
    maxPowerWatts: number | null;
    durationMs: number | null;
    sampleCount: number | null;
    scoreVariancePercent: number | null;
    warmupPassesCompleted: number | null;
    measuredPassesCompleted: number | null;
    currentPassType: string | null;
    currentPassIndex: number | null;
    currentPassTotal: number | null;
    currentPhase: string | null;
    currentPhaseIndex: number | null;
    currentPhaseTotal: number | null;
    progressPercent: number | null;
}

interface SoAIBenchRunRecord {
    runId: string;
    deviceId: string;
    profile: string;
    benchmarkMode: string;
    status: string;
    active: boolean;
    updateSeq: number;
    leaderboardEligible: boolean;
    leaderboardRejectionReason: string | null;
    failureReason: string | null;
    unsupportedReason: string | null;
    metrics: SoAIBenchRunMetrics;
    raw: JsonObject;
}

interface SoAIBenchRunModalHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    setHTML(target: Element, html: TrustedHtml): void;
    updateText(target: Element, text: string): void;
    addClassName(target: Element, className: string): void;
    removeClassName(target: Element, className: string): void;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void>;
    refreshSoAIBenchRuns(): Promise<JsonObject | null>;
    renderGpuControls(options?: { only?: string[] | null }): void;
    showSoAIBenchHistory(request: SoAIBenchRunOpenRequest): Promise<void>;
}

interface SoAIBenchRunModalDependencies {
    host: SoAIBenchRunModalHost;
}

interface SoAIBenchRunSession {
    deviceId: string;
    gpuIndex: string;
    gpuName: string;
    runId: string | null;
    updateSeq: number;
    token: symbol;
    cancelRequested: boolean;
    starting: boolean;
}

interface SoAIBenchRunRenderContext {
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchRunRecord | null;
    cancelRequested: boolean;
    terminalReason: string | null;
}

interface SoAIBenchRunProgressRuntime {
    reporter: OperationProgressReporter | null;
}

export type { SoAIBenchRunMetrics, SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunProgressRuntime, SoAIBenchRunRecord, SoAIBenchRunRenderContext, SoAIBenchRunSession };

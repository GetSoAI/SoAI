/* SoAI - SoAI Bench run modal public contracts [frontend/assets/ts/features/hardware/modals/soaibenchrun/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoAIBenchDeadline } from '@features/hardware/soaibenchLabels.ts';

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { GpuSoAIBenchPhaseDiagnostics } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
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
    phaseVariationPercent: GpuSoAIBenchPhaseDiagnostics | null;
    phaseDriftPercent: GpuSoAIBenchPhaseDiagnostics | null;
    warmupPassesCompleted: number | null;
    warmupActiveSeconds: number | null;
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
    gpuIndex: string | null;
    gpuName: string | null;
    profile: string;
    benchmarkMode: string;
    status: string;
    startedAtMs: number | null;
    stopRequestedAtMs: number | null;
    active: boolean;
    updateSeq: number;
    leaderboardEligible: boolean;
    leaderboardRejectionReason: string | null;
    legacy: boolean;
    publicationEligible: boolean;
    matchBasis: string | null;
    reasonMessage: string | null;
    deadline?: SoAIBenchDeadline;
    guidanceMessage: string | null;
    failureReason: string | null;
    unsupportedReason: string | null;
    metrics: SoAIBenchRunMetrics;
    raw: JsonObject;
}

type SoAIBenchRunSettlement = 'open' | 'rejected' | 'unresolved';

interface SoAIBenchRunEntry {
    readonly sectionId: string;
    readonly request: SoAIBenchRunOpenRequest;
    createdAtMs: number;
    runId: string | null;
    run: SoAIBenchRunRecord | null;
    stopPending: boolean;
    settlement: SoAIBenchRunSettlement;
    reason: string | null;
    recovering: boolean;
}

type SoAIBenchRunPhase = 'starting' | 'running' | 'stopping' | 'unresolved' | 'terminal' | 'rejected';
type SoAIBenchActivityState = 'starting' | 'running' | 'stopping' | 'unresolved';

interface SoAIBenchActivityProjection {
    hasActivity(): boolean;
    deviceActivity(deviceId: string | null): SoAIBenchActivityState | null;
}

interface SoAIBenchRunsFreshness {
    live: boolean;
    updatedAtMs: number | null;
}

type SoAIBenchComposer = { type: 'closed' } | { type: 'picker' } | { type: 'intro'; request: SoAIBenchRunOpenRequest; fromPicker: boolean };

interface SoAIBenchRunModalHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    setHTML(target: Element, html: TrustedHtml): void;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void>;
    refreshSoAIBenchRuns(): Promise<JsonObject | null>;
    showSoAIBenchHistory(request: SoAIBenchRunOpenRequest): Promise<void>;
}

interface SoAIBenchRunModalDependencies {
    host: SoAIBenchRunModalHost;
    publishRun(run: SoAIBenchRunRecord, setDisabled: (disabled: boolean) => void): Promise<void>;
}

export type { SoAIBenchActivityProjection, SoAIBenchActivityState, SoAIBenchComposer, SoAIBenchRunEntry, SoAIBenchRunMetrics, SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunPhase, SoAIBenchRunRecord, SoAIBenchRunsFreshness };

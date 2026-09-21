/* SoAI - Hardware feature export text [frontend/assets/ts/features/hardware/modals/soaibenchrun/exportText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { sanitizeDownloadFilename } from '@core/primitives/download.ts';
import { prettyJsonStringify } from '@core/serialization/json.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { formatGigabytes } from '@features/hardware/Formatters.ts';
import type { SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';
import type { SoAIBenchRunOpenRequest, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
import { projectSoAIBenchExportSystem, type SoAIBenchExportSystem } from '@features/hardware/modals/soaibenchrun/exportSystem.ts';
import { formatSoAIBenchCertification, formatSoAIBenchDuration, formatSoAIBenchMetric, formatSoAIBenchPercentValue, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchStartedAt, formatSoAIBenchTemperature, formatSoAIBenchThroughputValue, getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';
import { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchMatchBasisLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchReasonLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';
import { formatSoAIBenchTextTable } from '@features/hardware/soaibenchTextTable.ts';
import { buildSoAIBenchPhaseDiagnosticDisplays } from '@features/hardware/soaibenchPhaseDiagnostics.ts';
import type { GpuSoAIBenchPhaseDiagnostics } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';

interface SoAIBenchExportMetrics {
    overallScore: number | null;
    computeScore: number | null;
    memoryScore: number | null;
    latencyScore: number | null;
    computeGops: number | null;
    aluGops: number | null;
    matrixGops: number | null;
    memoryGbs: number | null;
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
    warmupActiveSeconds: number | null;
}

interface SoAIBenchExportRun {
    runId: string;
    profile: string;
    benchmarkMode: string;
    status: string;
    startedAtMs: number | null;
    leaderboardEligible: boolean;
    leaderboardRejectionReason: string | null;
    legacy: boolean;
    matchBasis: string | null;
    settingsSnapshotAvailable: boolean | null;
    staleHardware: boolean | null;
    reasonMessage: string | null;
    guidanceMessage: string | null;
    failureReason: string | null;
    unsupportedReason: string | null;
    metrics: SoAIBenchExportMetrics;
    system: SoAIBenchExportSystem;
    raw: JsonObject;
}

interface SoAIBenchRunExportInput {
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchExportRun;
    generatedAt: Date;
}

type TextTableRow = readonly [string, string];

const formatBenchmarkMode = (value: string): string => {
    return value ? formatUnexpectedSoAIBenchIdentifierLabel(value) : getSoAIBenchNotAvailableLabel();
};

const formatLatency = (value: number | null): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatSoAIBenchMetric(value, 1)} us`;
};

const appendOptionalBooleanRow = (rows: TextTableRow[], label: string, value: boolean | null): void => {
    if (value !== null) {
        rows.push([label, value ? i18n.t('common.yes') : i18n.t('common.no')]);
    }
};

const appendReasonRow = (rows: TextTableRow[], run: SoAIBenchExportRun): void => {
    const reason = resolveSoAIBenchReasonLabel(run.reasonMessage, run.failureReason, run.unsupportedReason, run.staleHardware === true);
    if (reason === null) {
        return;
    }
    const value = run.guidanceMessage ? `${reason} — ${run.guidanceMessage}` : reason;
    rows.push([i18n.t('hardware.modals.soaibenchHistory.columns.reason'), value]);
};

const formatRunSummaryTable = (input: SoAIBenchRunExportInput): string => {
    const run = input.run;
    const rows: TextTableRow[] = [
        [i18n.t('hardware.modals.soaibenchRun.export.generatedAt'), input.generatedAt.toISOString()],
        [i18n.t('hardware.modals.soaibenchRun.export.gpu'), i18n.t('hardware.gpu.panelHeader', { index: input.request.gpuIndex, name: input.request.gpuName })],
        [i18n.t('hardware.systemInfo.sections.cpu'), run.system.cpuName ?? getSoAIBenchNotAvailableLabel()],
        [i18n.t('hardware.systemInfo.sections.memory'), run.system.ramGb === null ? getSoAIBenchNotAvailableLabel() : formatGigabytes(run.system.ramGb)],
        [`SoAI ${i18n.t('about.version')}`, run.system.soaiVersion ?? getSoAIBenchNotAvailableLabel()],
        [i18n.t('hardware.modals.soaibenchRun.export.deviceId'), input.request.deviceId],
        [i18n.t('hardware.modals.soaibenchRun.export.runId'), run.runId],
        [i18n.t('hardware.modals.soaibenchRun.export.profile'), resolveSoAIBenchProfileLabel(run.profile)],
        [i18n.t('hardware.modals.soaibenchRun.export.mode'), formatBenchmarkMode(run.benchmarkMode)],
        [i18n.t('hardware.modals.soaibenchHistory.columns.started'), formatSoAIBenchStartedAt(run.startedAtMs)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.duration'), formatSoAIBenchDuration(run.metrics.durationMs)],
        [`${i18n.t('hardware.modals.soaibenchRun.progress.warmup')} · ${i18n.t('hardware.modals.soaibenchRun.metrics.duration')}`, run.metrics.warmupActiveSeconds === null ? getSoAIBenchNotAvailableLabel() : `${formatSoAIBenchMetric(run.metrics.warmupActiveSeconds, 1)} s`],
        [
            i18n.t('hardware.modals.soaibenchHistory.columns.certification'),
            formatSoAIBenchCertification({
                profile: run.profile,
                benchmarkMode: run.benchmarkMode,
                leaderboardEligible: run.leaderboardEligible,
                leaderboardRejectionReason: run.leaderboardRejectionReason,
                scoreVariancePercent: run.metrics.scoreVariancePercent,
                legacy: run.legacy
            })
        ],
        [i18n.t('hardware.modals.soaibenchHistory.columns.match'), resolveSoAIBenchMatchBasisLabel(run.matchBasis)]
    ];
    appendOptionalBooleanRow(rows, i18n.t('hardware.modals.soaibenchHistory.columns.settings'), run.settingsSnapshotAvailable);
    appendOptionalBooleanRow(rows, i18n.t('hardware.modals.soaibenchHistory.columns.stale'), run.staleHardware);
    appendReasonRow(rows, run);
    return formatSoAIBenchTextTable([i18n.t('hardware.modals.soaibenchRun.export.status'), resolveSoAIBenchStatusLabel(run.status)], rows);
};

const formatPerformanceTable = (run: SoAIBenchExportRun): string => {
    const metrics = run.metrics;
    const rows: TextTableRow[] = [
        [i18n.t('hardware.modals.soaibenchRun.metrics.computeScore'), formatSoAIBenchScore(metrics.computeScore)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.memoryScore'), formatSoAIBenchScore(metrics.memoryScore)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.latencyScore'), formatSoAIBenchScore(metrics.latencyScore)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.computeThroughput'), formatSoAIBenchThroughputValue(metrics.computeGops, 'GOPS')],
        [i18n.t('hardware.modals.soaibenchRun.metrics.aluThroughput'), formatSoAIBenchThroughputValue(metrics.aluGops, 'GOPS')],
        [i18n.t('hardware.modals.soaibenchRun.metrics.matrixThroughput'), formatSoAIBenchThroughputValue(metrics.matrixGops, 'GOPS')],
        [i18n.t('hardware.modals.soaibenchRun.metrics.memoryBandwidth'), formatSoAIBenchThroughputValue(metrics.memoryGbs, 'GB/s')],
        [i18n.t('hardware.modals.soaibenchRun.metrics.latency'), formatLatency(metrics.latencyUs)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.dispatchRate'), formatSoAIBenchThroughputValue(metrics.latencyDispatchesPerSecond, 'dispatch/s')],
        [i18n.t('hardware.modals.soaibenchRun.metrics.coreUsage'), formatSoAIBenchPercentValue(metrics.coreUtilizationPercent, 0)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.temperature'), formatSoAIBenchTemperature(metrics.maxTemperatureCelsius)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.power'), formatSoAIBenchPowerPair(metrics.avgPowerWatts, metrics.maxPowerWatts)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.sampleCount'), formatSoAIBenchScore(metrics.sampleCount)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.scoreVariance'), formatSoAIBenchPercentValue(metrics.scoreVariancePercent, 2)]
    ];
    for (const diagnostic of buildSoAIBenchPhaseDiagnosticDisplays(metrics.phaseVariationPercent, metrics.phaseDriftPercent)) {
        rows.push([`${diagnostic.phaseLabel} · ${i18n.t('hardware.modals.soaibenchRun.metrics.variationAndDrift')}`, diagnostic.value]);
    }
    return formatSoAIBenchTextTable([i18n.t('hardware.modals.soaibenchRun.scoreLabel'), formatSoAIBenchScore(metrics.overallScore)], rows);
};

const formatRawRun = (raw: JsonObject): string => {
    return prettyJsonStringify(raw)
        .split('\n')
        .map((value) => `    ${value}`)
        .join('\n');
};

const formatSoAIBenchRunExportText = (input: SoAIBenchRunExportInput): string => {
    return [`# ${i18n.t('hardware.modals.soaibenchRun.export.title')}`, `## ${i18n.t('hardware.modals.soaibenchRun.scoreLabel')}: ${formatSoAIBenchScore(input.run.metrics.overallScore)}`, formatRunSummaryTable(input), formatPerformanceTable(input.run), `## ${i18n.t('hardware.modals.soaibenchRun.export.rawRun')}`, formatRawRun(input.run.raw), ''].join('\n\n');
};

const exportRunFromHistoryRun = (run: SoAIBenchHistoryRun): SoAIBenchExportRun => ({
    runId: run.runId,
    profile: run.profile,
    benchmarkMode: run.benchmarkMode,
    status: run.status,
    startedAtMs: run.startedAtMs,
    leaderboardEligible: run.leaderboardEligible,
    leaderboardRejectionReason: run.leaderboardRejectionReason,
    legacy: run.legacy,
    matchBasis: run.matchBasis,
    settingsSnapshotAvailable: run.settingsSnapshotAvailable,
    staleHardware: run.staleHardware,
    reasonMessage: run.reasonMessage,
    guidanceMessage: run.guidanceMessage,
    failureReason: run.failureReason,
    unsupportedReason: run.unsupportedReason,
    metrics: {
        ...run.telemetry,
        durationMs: run.durationMs,
        scoreVariancePercent: run.scoreVariancePercent,
        phaseVariationPercent: run.phaseVariationPercent,
        phaseDriftPercent: run.phaseDriftPercent,
        warmupActiveSeconds: run.warmupActiveSeconds
    },
    system: projectSoAIBenchExportSystem(run.raw),
    raw: run.raw
});

const exportRunFromRunRecord = (run: SoAIBenchRunRecord): SoAIBenchExportRun => ({
    runId: run.runId,
    profile: run.profile,
    benchmarkMode: run.benchmarkMode,
    status: run.status,
    startedAtMs: run.startedAtMs,
    leaderboardEligible: run.leaderboardEligible,
    leaderboardRejectionReason: run.leaderboardRejectionReason,
    legacy: run.legacy,
    matchBasis: run.matchBasis,
    settingsSnapshotAvailable: null,
    staleHardware: null,
    reasonMessage: run.reasonMessage,
    guidanceMessage: run.guidanceMessage,
    failureReason: run.failureReason,
    unsupportedReason: run.unsupportedReason,
    metrics: run.metrics,
    system: projectSoAIBenchExportSystem(run.raw),
    raw: run.raw
});

const buildSoAIBenchRunExportFilename = (run: SoAIBenchExportRun, timestamp: string): string => {
    return `${sanitizeDownloadFilename(`soai-soaibench-${run.runId}-${timestamp}`, 'soai-soaibench-run', 137)}.md`;
};

export { buildSoAIBenchRunExportFilename, exportRunFromHistoryRun, exportRunFromRunRecord, formatSoAIBenchRunExportText };
export type { SoAIBenchExportRun, SoAIBenchRunExportInput };

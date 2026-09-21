/* SoAI - Hardware feature formatting [frontend/assets/ts/features/hardware/modals/soaibenchhistory/formatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatHardwareNumber } from '@features/hardware/Formatters.ts';
import { SOAIBENCH_HISTORY_COLUMNS, resolveSoAIBenchHistoryColumnLabel } from '@features/hardware/modals/soaibenchhistory/columns.ts';
import type { SoAIBenchHistoryDisplayRow, SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';
import { formatSoAIBenchCertification, formatSoAIBenchDuration, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchStartedAt, formatSoAIBenchTemperature, getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';
import { resolveSoAIBenchMatchBasisLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchReasonLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';
import { buildSoAIBenchPhaseDiagnosticDisplays } from '@features/hardware/soaibenchPhaseDiagnostics.ts';

type PhaseLabelKey = 'alu' | 'compute' | 'latency' | 'matrix' | 'memory';

const phaseLabel = (key: PhaseLabelKey): string => {
    switch (key) {
        case 'alu':
            return i18n.t('hardware.modals.soaibenchHistory.phaseLabels.alu');
        case 'compute':
            return i18n.t('hardware.modals.soaibenchHistory.phaseLabels.compute');
        case 'latency':
            return i18n.t('hardware.modals.soaibenchHistory.phaseLabels.latency');
        case 'matrix':
            return i18n.t('hardware.modals.soaibenchHistory.phaseLabels.matrix');
        case 'memory':
            return i18n.t('hardware.modals.soaibenchHistory.phaseLabels.memory');
    }
    const unhandledKey: never = key;
    return unhandledKey;
};

const formatPhaseRate = (label: string, value: number | null, decimals: number, unit: string): string | null => {
    return value === null ? null : `${label} ${formatHardwareNumber(value, decimals)} ${unit}`;
};

const formatPhaseLatency = (value: number | null): string | null => {
    if (value === null) {
        return null;
    }
    return `${phaseLabel('latency')} ${formatHardwareNumber(value, 1)} us`;
};

const appendPhase = (phases: string[], value: string | null): void => {
    if (value !== null) {
        phases.push(value);
    }
};

const formatPhases = (run: SoAIBenchHistoryRun): string => {
    const phases: string[] = [];
    appendPhase(phases, formatPhaseRate(phaseLabel('compute'), run.telemetry.computeGops, 0, 'GOPS'));
    appendPhase(phases, formatPhaseRate(phaseLabel('alu'), run.telemetry.aluGops, 0, 'GOPS'));
    appendPhase(phases, formatPhaseRate(phaseLabel('matrix'), run.telemetry.matrixGops, 0, 'GOPS'));
    appendPhase(phases, formatPhaseRate(phaseLabel('memory'), run.telemetry.memoryGbs, 0, 'GB/s'));
    appendPhase(phases, formatPhaseLatency(run.telemetry.latencyUs));
    return phases.length > 0 ? phases.join(' | ') : getSoAIBenchNotAvailableLabel();
};

const formatPhaseDiagnostics = (run: SoAIBenchHistoryRun): string => {
    const diagnostics = buildSoAIBenchPhaseDiagnosticDisplays(run.phaseVariationPercent, run.phaseDriftPercent);
    return diagnostics.length > 0 ? diagnostics.map((diagnostic) => `${diagnostic.phaseLabel} ${diagnostic.value}`).join(' | ') : getSoAIBenchNotAvailableLabel();
};

const formatHistoryColumnLabels = (): string[] => {
    return SOAIBENCH_HISTORY_COLUMNS.map((column) => resolveSoAIBenchHistoryColumnLabel(column.key));
};

const formatHistoryRowColumns = (run: SoAIBenchHistoryRun): string[] => {
    const columns: string[] = [];
    columns.push(formatSoAIBenchStartedAt(run.startedAtMs));
    columns.push(resolveSoAIBenchProfileLabel(run.profile));
    columns.push(resolveSoAIBenchStatusLabel(run.status));
    columns.push(formatSoAIBenchScore(run.telemetry.overallScore));
    columns.push(formatPhases(run));
    columns.push(formatPhaseDiagnostics(run));
    columns.push(formatSoAIBenchCertification(run));
    columns.push(formatSoAIBenchTemperature(run.telemetry.maxTemperatureCelsius));
    columns.push(formatSoAIBenchPowerPair(run.telemetry.avgPowerWatts, run.telemetry.maxPowerWatts));
    columns.push(formatSoAIBenchDuration(run.durationMs));
    columns.push(resolveSoAIBenchMatchBasisLabel(run.matchBasis));
    columns.push(run.settingsSnapshotAvailable ? i18n.t('common.yes') : i18n.t('common.no'));
    columns.push(run.staleHardware ? i18n.t('common.yes') : i18n.t('common.no'));
    columns.push(resolveSoAIBenchReasonLabel(run.reasonMessage, run.failureReason, run.unsupportedReason, run.staleHardware) ?? getSoAIBenchNotAvailableLabel());
    return columns;
};

const formatHistoryRows = (runs: readonly SoAIBenchHistoryRun[]): SoAIBenchHistoryDisplayRow[] => {
    return runs.map((run) => ({
        runId: run.runId,
        publicationEligible: run.publicationEligible,
        localDeletionEligible: run.status !== 'running',
        columns: formatHistoryRowColumns(run),
        raw: run.raw
    }));
};

export { formatHistoryColumnLabels, formatHistoryRows };

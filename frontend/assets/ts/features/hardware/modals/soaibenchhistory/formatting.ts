/* SoAI - Hardware feature formatting [frontend/assets/ts/features/hardware/modals/soaibenchhistory/formatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPositiveEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { formatHardwareNumber } from '@features/hardware/Formatters.ts';
import { SOAIBENCH_HISTORY_COLUMNS, resolveSoAIBenchHistoryColumnLabel } from '@features/hardware/modals/soaibenchhistory/columns.ts';
import type { SoAIBenchHistoryDisplayRow, SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';
import { formatSoAIBenchDuration, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchTemperature, getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';
import { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';

const resolveMatchBasisLabel = (value: string | null): string => {
    if (!value) {
        return getSoAIBenchNotAvailableLabel();
    }
    switch (value) {
        case 'device_id':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.device_id');
        case 'gpu_uuid':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.gpu_uuid');
        case 'pci_bdf':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.pci_bdf');
        case 'gpu_model_key':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.gpu_model_key');
        case 'vendor_name':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.vendor_name');
        case 'vendor_name_ordinal':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.vendor_name_ordinal');
        case 'stale':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.stale');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

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

const formatVariance = (value: number | null): string => {
    return value === null ? '' : ` (${i18n.t('hardware.modals.soaibenchHistory.certification.varianceSuffix', { variance: formatHardwareNumber(value, 1) })})`;
};

const formatCertification = (run: SoAIBenchHistoryRun): string => {
    if (run.profile !== 'standard') {
        return getSoAIBenchNotAvailableLabel();
    }
    if (run.benchmarkMode !== 'certified') {
        return i18n.t('hardware.modals.soaibenchHistory.certification.quick');
    }
    if (run.leaderboardEligible) {
        return `${i18n.t('hardware.modals.soaibenchHistory.certification.certified')}${formatVariance(run.scoreVariancePercent)}`;
    }
    const reason = formatUnexpectedSoAIBenchIdentifierLabel(run.leaderboardRejectionReason);
    const label = i18n.t('hardware.modals.soaibenchHistory.certification.ineligible', { reason });
    return `${label}${formatVariance(run.scoreVariancePercent)}`;
};

const formatStartedAt = (value: number | null): string => {
    return formatPositiveEpochMsMinuteWithFallback(value, getSoAIBenchNotAvailableLabel());
};

const formatReason = (run: SoAIBenchHistoryRun): string => {
    const rawReason = run.failureReason || run.unsupportedReason;
    if (rawReason) {
        return formatUnexpectedSoAIBenchIdentifierLabel(rawReason);
    }
    if (run.staleHardware) {
        return i18n.t('hardware.modals.soaibenchHistory.staleHardware');
    }
    return getSoAIBenchNotAvailableLabel();
};

const formatHistoryColumnLabels = (): string[] => {
    return SOAIBENCH_HISTORY_COLUMNS.map((column) => resolveSoAIBenchHistoryColumnLabel(column.key));
};

const formatHistoryRowColumns = (run: SoAIBenchHistoryRun): string[] => {
    const columns: string[] = [];
    columns.push(resolveSoAIBenchProfileLabel(run.profile));
    columns.push(resolveSoAIBenchStatusLabel(run.status));
    columns.push(formatSoAIBenchScore(run.telemetry.overallScore));
    columns.push(formatPhases(run));
    columns.push(formatCertification(run));
    columns.push(formatSoAIBenchTemperature(run.telemetry.maxTemperatureCelsius));
    columns.push(formatSoAIBenchPowerPair(run.telemetry.avgPowerWatts, run.telemetry.maxPowerWatts));
    columns.push(formatSoAIBenchDuration(run.durationMs));
    columns.push(formatStartedAt(run.startedAtMs));
    columns.push(resolveMatchBasisLabel(run.matchBasis));
    columns.push(run.settingsSnapshotAvailable ? i18n.t('common.yes') : i18n.t('common.no'));
    columns.push(run.staleHardware ? i18n.t('common.yes') : i18n.t('common.no'));
    columns.push(formatReason(run));
    return columns;
};

const formatHistoryRows = (runs: readonly SoAIBenchHistoryRun[]): SoAIBenchHistoryDisplayRow[] => {
    return runs.map((run) => ({
        runId: run.runId,
        columns: formatHistoryRowColumns(run)
    }));
};

export { formatHistoryColumnLabels, formatHistoryRows };

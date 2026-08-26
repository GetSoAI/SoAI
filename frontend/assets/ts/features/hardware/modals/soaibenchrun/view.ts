/* SoAI - SoAI Bench run modal rendering [frontend/assets/ts/features/hardware/modals/soaibenchrun/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { uiText } from '@core/security/uiHtml.ts';
import { formatHardwareNumber } from '@features/hardware/Formatters.ts';
import { formatSoAIBenchDuration, formatSoAIBenchMetric, formatSoAIBenchPercentValue, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchTemperature, formatSoAIBenchThroughputValue, getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';
import { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';
import { resolveTemperatureSeverity } from '@features/hardware/thermalSeverity.ts';
import type { SoAIBenchRunRecord, SoAIBenchRunRenderContext } from '@features/hardware/modals/soaibenchrun/types.ts';

const MEASURED_PASS_COUNT = 5;
const REPORT_GRID_COLUMNS = 4;

interface SummaryBadge {
    label: string;
    className: string;
}

const temperatureMetricClass = (value: number | null): string => {
    const severity = resolveTemperatureSeverity(value);
    if (severity === 'critical') return 'hardware-soaibench-report-metric--temperature-error';
    if (severity === 'warning') return 'hardware-soaibench-report-metric--temperature-warning';
    return '';
};

const phaseLabel = (phase: string | null): string | null => {
    if (phase === 'compute') {
        return i18n.t('hardware.modals.soaibenchRun.phases.compute');
    }
    if (phase === 'alu') {
        return i18n.t('hardware.modals.soaibenchRun.phases.alu');
    }
    if (phase === 'matrix') {
        return i18n.t('hardware.modals.soaibenchRun.phases.matrix');
    }
    if (phase === 'latency') {
        return i18n.t('hardware.modals.soaibenchRun.phases.latency');
    }
    if (phase === 'memory') {
        return i18n.t('hardware.modals.soaibenchRun.phases.memory');
    }
    if (phase === 'stability') {
        return i18n.t('hardware.modals.soaibenchRun.phases.stability');
    }
    return null;
};

const summaryBadgeForRun = (run: SoAIBenchRunRecord | null): SummaryBadge => {
    if (run === null) {
        return { label: i18n.t('hardware.modals.soaibenchRun.standardRun'), className: 'status-green' };
    }
    if (run.status === 'completed') {
        return { label: resolveSoAIBenchStatusLabel(run.status), className: 'status-green' };
    }
    if (run.status === 'running') {
        return { label: resolveSoAIBenchStatusLabel(run.status), className: 'status-orange' };
    }
    if (run.status === 'cancelled' || run.status === 'stopped') {
        return { label: resolveSoAIBenchStatusLabel(run.status), className: 'status-red' };
    }
    if (run.status === 'failed' || run.status === 'unsupported' || run.status === 'unstable' || run.status === 'indeterminate') {
        return { label: resolveSoAIBenchStatusLabel(run.status), className: 'status-red' };
    }
    return { label: i18n.t('hardware.modals.soaibenchRun.standardRun'), className: 'status-grey' };
};

const scoreTextForRun = (run: SoAIBenchRunRecord): string => {
    if (run.metrics.overallScore !== null) {
        return formatSoAIBenchScore(run.metrics.overallScore);
    }
    if (run.status === 'cancelled' || run.status === 'stopped') {
        return formatSoAIBenchScore(0);
    }
    return resolveSoAIBenchStatusLabel(run.status);
};

const currentPhaseLabel = (run: SoAIBenchRunRecord): string | null => phaseLabel(run.metrics.currentPhase);

const statusMetricClass = (status: string): string => {
    if (status === 'completed') {
        return 'hardware-soaibench-report-metric--status-success';
    }
    if (status === 'running') {
        return 'hardware-soaibench-report-metric--status-info';
    }
    if (status === 'cancelled' || status === 'stopped') {
        return 'hardware-soaibench-report-metric--status-warning';
    }
    if (status === 'failed' || status === 'unsupported' || status === 'unstable' || status === 'indeterminate') {
        return 'hardware-soaibench-report-metric--status-error';
    }
    return '';
};

const reasonForRun = (run: SoAIBenchRunRecord): string | null => {
    const reason = run.failureReason || run.unsupportedReason || run.leaderboardRejectionReason;
    return reason ? formatUnexpectedSoAIBenchIdentifierLabel(reason) : null;
};

const shouldShowReasonPanel = (run: SoAIBenchRunRecord): boolean => {
    return run.status === 'failed' || run.status === 'unsupported' || run.status === 'unstable' || run.status === 'cancelled' || run.status === 'stopped';
};

const renderSummaryBand = (context: SoAIBenchRunRenderContext): string => {
    const gpuLabel = i18n.t('hardware.gpu.panelHeader', { index: context.request.gpuIndex, name: context.request.gpuName });
    const badge = summaryBadgeForRun(context.run);
    return `<div class="hardware-soaibench-run-summary"><div class="hardware-soaibench-run-gpu">${uiText(gpuLabel).html}</div><span class="ui-status-badge ${badge.className}">${uiText(badge.label).html}</span></div>`;
};

const renderIntroSection = (title: string, itemsText: string): string => {
    const items = itemsText
        .split('|')
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    const list = items.map((item) => `<li>${uiText(item).html}</li>`).join('');
    return `<section class="hardware-soaibench-run-section"><h3>${uiText(title).html}</h3><ul>${list}</ul></section>`;
};

const renderRunIntro = (context: SoAIBenchRunRenderContext) => {
    return toTrustedUiHtml(`${renderSummaryBand(context)}<div class="hardware-soaibench-run-grid">` + renderIntroSection(i18n.t('hardware.modals.soaibenchRun.sections.measures.title'), i18n.t('hardware.modals.soaibenchRun.sections.measures.items')) + renderIntroSection(i18n.t('hardware.modals.soaibenchRun.sections.runs.title'), i18n.t('hardware.modals.soaibenchRun.sections.runs.items')) + renderIntroSection(i18n.t('hardware.modals.soaibenchRun.sections.expect.title'), i18n.t('hardware.modals.soaibenchRun.sections.expect.items')) + `</div>`);
};

const renderRunProgressShell = (context: SoAIBenchRunRenderContext) => {
    return toTrustedUiHtml(`${renderSummaryBand(context)}<div class="hardware-soaibench-progress-host" id="hardware-soaibench-run-modal-progress"></div>`);
};

const renderMetricItem = (label: string, value: string, index: number, severityClass: string): string => {
    const checkerboardClass = resolveCheckerboardClass(index, { columns: REPORT_GRID_COLUMNS, start: 'checkerboard-dark' });
    const classes = severityClass ? `hardware-soaibench-report-metric ${checkerboardClass} ${severityClass}` : `hardware-soaibench-report-metric ${checkerboardClass}`;
    return `<div class="${classes}"><span>${uiText(label).html}</span><strong>${uiText(value).html}</strong></div>`;
};

const renderReportMetrics = (run: SoAIBenchRunRecord): string => {
    const entries: [string, string, string][] = [
        [i18n.t('hardware.modals.soaibenchRun.metrics.status'), resolveSoAIBenchStatusLabel(run.status), statusMetricClass(run.status)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.duration'), formatSoAIBenchDuration(run.metrics.durationMs), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.sampleCount'), formatSoAIBenchScore(run.metrics.sampleCount), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.scoreVariance'), formatSoAIBenchPercentValue(run.metrics.scoreVariancePercent, 2), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.computeScore'), formatSoAIBenchScore(run.metrics.computeScore), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.memoryScore'), formatSoAIBenchScore(run.metrics.memoryScore), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.latencyScore'), formatSoAIBenchScore(run.metrics.latencyScore), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.dispatchRate'), formatSoAIBenchThroughputValue(run.metrics.latencyDispatchesPerSecond, 'dispatch/s'), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.computeThroughput'), formatSoAIBenchThroughputValue(run.metrics.computeGops, 'GOPS'), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.aluThroughput'), formatSoAIBenchThroughputValue(run.metrics.aluGops, 'GOPS'), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.matrixThroughput'), formatSoAIBenchThroughputValue(run.metrics.matrixGops, 'GOPS'), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.memoryBandwidth'), formatSoAIBenchThroughputValue(run.metrics.memoryGbs, 'GB/s'), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.latency'), `${formatSoAIBenchMetric(run.metrics.latencyUs, 1)} us`, ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.coreUsage'), formatSoAIBenchPercentValue(run.metrics.coreUtilizationPercent, 0), ''],
        [i18n.t('hardware.modals.soaibenchRun.metrics.temperature'), formatSoAIBenchTemperature(run.metrics.maxTemperatureCelsius), temperatureMetricClass(run.metrics.maxTemperatureCelsius)],
        [i18n.t('hardware.modals.soaibenchRun.metrics.power'), formatSoAIBenchPowerPair(run.metrics.avgPowerWatts, run.metrics.maxPowerWatts), '']
    ];
    return entries.map(([label, value, severityClass], index) => renderMetricItem(label, value, index, severityClass)).join('');
};

const renderRunReport = (context: SoAIBenchRunRenderContext) => {
    const run = context.run;
    if (!run) {
        const reasonPanel = context.terminalReason ? `<div class="hardware-soaibench-run-reason" data-tone="warning">${uiText(context.terminalReason).html}</div>` : '';
        const statusText = context.terminalReason ? i18n.t('hardware.modals.soaibenchRun.progress.startFailed') : getSoAIBenchNotAvailableLabel();
        return toTrustedUiHtml(`${renderSummaryBand(context)}<div class="hardware-soaibench-report"><div class="hardware-soaibench-report-band"><span>${uiText(i18n.t('hardware.modals.soaibenchRun.scoreLabel')).html}</span><strong>${uiText(statusText).html}</strong></div>${reasonPanel}</div>`);
    }
    const reason = reasonForRun(run);
    const reasonPanel = reason && shouldShowReasonPanel(run) ? `<div class="hardware-soaibench-run-reason" data-tone="warning">${uiText(reason).html}</div>` : '';
    const scoreText = scoreTextForRun(run);
    return toTrustedUiHtml(`${renderSummaryBand(context)}<div class="hardware-soaibench-report"><div class="hardware-soaibench-report-band"><span>${uiText(i18n.t('hardware.modals.soaibenchRun.scoreLabel')).html}</span><strong>${uiText(scoreText).html}</strong></div><div class="hardware-soaibench-report-grid">${renderReportMetrics(run)}</div>${reasonPanel}</div>`);
};

const progressMessageForRun = (run: SoAIBenchRunRecord | null, cancelRequested: boolean): string => {
    if (cancelRequested) {
        return i18n.t('hardware.modals.soaibenchRun.progress.stopping');
    }
    if (!run) {
        return i18n.t('hardware.modals.soaibenchRun.progress.starting');
    }
    const measured = run.metrics.measuredPassesCompleted;
    const currentPhase = currentPhaseLabel(run);
    if (currentPhase !== null && run.metrics.currentPassType === 'warmup') {
        return i18n.t('hardware.modals.soaibenchRun.progress.warmupPhase', { phase: currentPhase });
    }
    if (currentPhase !== null && run.metrics.currentPassType === 'measured' && run.metrics.currentPassIndex !== null) {
        return i18n.t('hardware.modals.soaibenchRun.progress.measuredPhase', { pass: Math.min(run.metrics.currentPassIndex, MEASURED_PASS_COUNT), total: MEASURED_PASS_COUNT, phase: currentPhase });
    }
    if (measured !== null && measured > 0) {
        return i18n.t('hardware.modals.soaibenchRun.progress.measured', { pass: Math.min(measured, MEASURED_PASS_COUNT), total: MEASURED_PASS_COUNT });
    }
    const warmup = run.metrics.warmupPassesCompleted;
    if (warmup !== null && warmup > 0) {
        return i18n.t('hardware.modals.soaibenchRun.progress.warmup');
    }
    return i18n.t('hardware.modals.soaibenchRun.progress.running');
};

const progressPercentForRun = (run: SoAIBenchRunRecord | null): number => {
    if (!run) {
        return 0;
    }
    if (run.status !== 'running') {
        return 100;
    }
    if (run.metrics.progressPercent !== null) {
        return clampNumber(run.metrics.progressPercent, 0, 100);
    }
    const measured = run.metrics.measuredPassesCompleted ?? 0;
    const warmup = run.metrics.warmupPassesCompleted ?? 0;
    return Math.max(warmup > 0 ? 5 : 0, measured > 0 ? 10 + Math.min(measured, MEASURED_PASS_COUNT) * 16 : 0);
};

const progressDetailsForRun = (run: SoAIBenchRunRecord | null): string => {
    if (!run) {
        return i18n.t('hardware.modals.soaibenchRun.progress.awaitingRun');
    }
    const details: string[] = [];
    const currentPhase = currentPhaseLabel(run);
    if (currentPhase !== null && run.metrics.currentPassType === 'warmup') {
        const passIndex = run.metrics.currentPassIndex ?? 1;
        const passTotal = run.metrics.currentPassTotal ?? 1;
        const phaseIndex = run.metrics.currentPhaseIndex ?? 1;
        const phaseTotal = run.metrics.currentPhaseTotal ?? 1;
        details.push(i18n.t('hardware.modals.soaibenchRun.progress.warmupDetail', { pass: passIndex, total: passTotal }));
        details.push(i18n.t('hardware.modals.soaibenchRun.progress.phaseDetail', { phase: currentPhase, index: phaseIndex, total: phaseTotal }));
    } else if (currentPhase !== null && run.metrics.currentPassType === 'measured' && run.metrics.currentPassIndex !== null) {
        const phaseIndex = run.metrics.currentPhaseIndex ?? 1;
        const phaseTotal = run.metrics.currentPhaseTotal ?? 1;
        details.push(i18n.t('hardware.modals.soaibenchRun.progress.measuredDetail', { pass: Math.min(run.metrics.currentPassIndex, MEASURED_PASS_COUNT), total: MEASURED_PASS_COUNT }));
        details.push(i18n.t('hardware.modals.soaibenchRun.progress.phaseDetail', { phase: currentPhase, index: phaseIndex, total: phaseTotal }));
    } else {
        const measured = run.metrics.measuredPassesCompleted;
        if (measured !== null) {
            details.push(i18n.t('hardware.modals.soaibenchRun.progress.measuredDetail', { pass: Math.min(measured, MEASURED_PASS_COUNT), total: MEASURED_PASS_COUNT }));
        }
    }
    if (run.metrics.coreUtilizationPercent !== null) {
        details.push(`${i18n.t('hardware.gpu.telemetry.coreUtilization')} ${formatSoAIBenchPercentValue(run.metrics.coreUtilizationPercent, 0)}`);
    }
    if (run.metrics.maxTemperatureCelsius !== null) {
        details.push(formatSoAIBenchTemperature(run.metrics.maxTemperatureCelsius));
    }
    if (run.metrics.avgPowerWatts !== null) {
        details.push(`${formatHardwareNumber(run.metrics.avgPowerWatts, 1)} W`);
    }
    return details.length ? details.join(' | ') : resolveSoAIBenchStatusLabel(run.status);
};

export { progressDetailsForRun, progressMessageForRun, progressPercentForRun, renderRunIntro, renderRunProgressShell, renderRunReport };

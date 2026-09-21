/* SoAI - Hardware feature SoAIBench phase diagnostics [frontend/assets/ts/features/hardware/soaibenchPhaseDiagnostics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchPhaseDiagnostics } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatSoAIBenchPercentValue, formatSoAIBenchSignedPercentValue } from '@features/hardware/soaibenchMetricFormatting.ts';

interface SoAIBenchPhaseDiagnosticDisplay {
    phaseLabel: string;
    value: string;
}

const diagnosticDisplay = (phaseLabel: string, variationPercent: number, driftPercent: number): SoAIBenchPhaseDiagnosticDisplay => ({
    phaseLabel,
    value: `${formatSoAIBenchPercentValue(variationPercent, 2)} / ${formatSoAIBenchSignedPercentValue(driftPercent, 2)}`
});

const buildSoAIBenchPhaseDiagnosticDisplays = (variation: GpuSoAIBenchPhaseDiagnostics | null, drift: GpuSoAIBenchPhaseDiagnostics | null): SoAIBenchPhaseDiagnosticDisplay[] => {
    if (variation === null || drift === null) return [];
    return [diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.alu'), variation.alu, drift.alu), diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.compute'), variation.compute, drift.compute), diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.matrix'), variation.matrix, drift.matrix), diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.latency'), variation.latency, drift.latency), diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.memory'), variation.memory, drift.memory), diagnosticDisplay(i18n.t('hardware.modals.soaibenchRun.phases.stability'), variation.mixed, drift.mixed)];
};

export { buildSoAIBenchPhaseDiagnosticDisplays };
export type { SoAIBenchPhaseDiagnosticDisplay };

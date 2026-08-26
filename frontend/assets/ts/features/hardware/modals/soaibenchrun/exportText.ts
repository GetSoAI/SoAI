/* SoAI - Hardware feature export text [frontend/assets/ts/features/hardware/modals/soaibenchrun/exportText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';
import type { SoAIBenchRunOpenRequest, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
import { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';

interface SoAIBenchExportRun {
    runId: string;
    profile: string;
    benchmarkMode: string;
    status: string;
    raw: JsonObject;
}

interface SoAIBenchRunExportInput {
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchExportRun;
    generatedAt: Date;
}

const line = (label: string, value: string): string => `${label}: ${value}`;

const normalizeBenchmarkMode = (value: string): string => {
    return value ? formatUnexpectedSoAIBenchIdentifierLabel(value) : i18n.t('common.notAvailableShort');
};

const formatSoAIBenchRunExportText = (input: SoAIBenchRunExportInput): string => {
    const run = input.run;
    const sections = [i18n.t('hardware.modals.soaibenchRun.export.title'), '', line(i18n.t('hardware.modals.soaibenchRun.export.generatedAt'), input.generatedAt.toISOString()), line(i18n.t('hardware.modals.soaibenchRun.export.gpu'), i18n.t('hardware.gpu.panelHeader', { index: input.request.gpuIndex, name: input.request.gpuName })), line(i18n.t('hardware.modals.soaibenchRun.export.deviceId'), input.request.deviceId), line(i18n.t('hardware.modals.soaibenchRun.export.runId'), run.runId), line(i18n.t('hardware.modals.soaibenchRun.export.profile'), resolveSoAIBenchProfileLabel(run.profile)), line(i18n.t('hardware.modals.soaibenchRun.export.mode'), normalizeBenchmarkMode(run.benchmarkMode)), line(i18n.t('hardware.modals.soaibenchRun.export.status'), resolveSoAIBenchStatusLabel(run.status)), '', i18n.t('hardware.modals.soaibenchRun.export.rawRun'), stableJsonStringify(run.raw)];
    return `${sections.join('\n')}\n`;
};

const exportRunFromHistoryRun = (run: SoAIBenchHistoryRun): SoAIBenchExportRun => ({
    runId: run.runId,
    profile: run.profile,
    benchmarkMode: run.benchmarkMode,
    status: run.status,
    raw: run.raw
});

const exportRunFromRunRecord = (run: SoAIBenchRunRecord): SoAIBenchExportRun => ({
    runId: run.runId,
    profile: run.profile,
    benchmarkMode: run.benchmarkMode,
    status: run.status,
    raw: run.raw
});

const buildSoAIBenchRunExportFilename = (run: SoAIBenchExportRun, timestamp: string): string => {
    return `soai-soaibench-${run.runId}-${timestamp}.txt`;
};

export { buildSoAIBenchRunExportFilename, exportRunFromHistoryRun, exportRunFromRunRecord, formatSoAIBenchRunExportText };
export type { SoAIBenchExportRun, SoAIBenchRunExportInput };

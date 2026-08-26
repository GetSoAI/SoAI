/* SoAI - Hardware feature markdown [frontend/assets/ts/features/hardware/modals/soaibenchhistory/markdown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { capitalize } from '@core/primitives/text.ts';
import { i18n } from '@core/i18n/index.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { formatHistoryColumnLabels } from '@features/hardware/modals/soaibenchhistory/formatting.ts';
import type { SoAIBenchHistoryDisplayRow, SoAIBenchHistoryOpenRequest } from '@features/hardware/modals/soaibenchhistory/types.ts';

interface SoAIBenchHistoryMarkdownInput {
    request: SoAIBenchHistoryOpenRequest;
    runCount: number;
    rows: readonly SoAIBenchHistoryDisplayRow[];
    systemInfo: JsonObject;
    hardware: JsonObject;
}

const NOT_AVAILABLE = (): string => i18n.t('common.notAvailableShort');

const escapeMarkdownCell = (value: string): string => {
    return value.replace(/\|/g, '\\|').replace(/\n/g, ' ').trim();
};

const resolveSnapshotRecord = (value: JsonValue | undefined): JsonObject => {
    return isJsonObject(value) ? value : {};
};

const resolveSoAIVersion = (systemInfo: JsonObject): string => {
    return toTrimmedString(systemInfo['soai_version']) || NOT_AVAILABLE();
};

const resolvePlatform = (hardware: JsonObject): string => {
    const capabilities = resolveSnapshotRecord(hardware['capabilities']);
    const platform = toTrimmedString(capabilities['platform']);
    return platform ? capitalize(platform) : NOT_AVAILABLE();
};

const formatMetadataLines = (input: SoAIBenchHistoryMarkdownInput): string[] => {
    return [`- ${i18n.t('about.version')}: ${escapeMarkdownCell(resolveSoAIVersion(input.systemInfo))}`, `- ${i18n.t('about.platform')}: ${escapeMarkdownCell(resolvePlatform(input.hardware))}`, `- ${i18n.t('hardware.components.gpu')}: ${escapeMarkdownCell(i18n.t('hardware.gpu.panelHeader', { index: input.request.gpuIndex, name: input.request.gpuName }))}`, `- ${i18n.t('hardware.modals.soaibenchHistory.copyFields.deviceId')}: ${escapeMarkdownCell(input.request.deviceId)}`, `- ${i18n.t('hardware.modals.soaibenchHistory.copyFields.runs')}: ${escapeMarkdownCell(String(input.runCount))}`];
};

const formatMarkdownTable = (rows: readonly SoAIBenchHistoryDisplayRow[]): string => {
    const headers = formatHistoryColumnLabels().map((label) => escapeMarkdownCell(label));
    const separator = headers.map(() => '---');
    const lines = [`| ${headers.join(' | ')} |`, `| ${separator.join(' | ')} |`];
    for (const row of rows) {
        lines.push(`| ${row.columns.map((column) => escapeMarkdownCell(column)).join(' | ')} |`);
    }
    return lines.join('\n');
};

const formatSoAIBenchHistoryMarkdown = (input: SoAIBenchHistoryMarkdownInput): string => {
    const sections = [`# ${i18n.t('hardware.modals.soaibenchHistory.title')}`, formatMetadataLines(input).join('\n')];
    if (input.rows.length <= 0) {
        sections.push(`## ${i18n.t('hardware.modals.soaibenchHistory.copyFields.table')}`, i18n.t('hardware.modals.soaibenchHistory.empty'));
        return sections.join('\n\n');
    }
    sections.push(`## ${i18n.t('hardware.modals.soaibenchHistory.copyFields.table')}`, formatMarkdownTable(input.rows));
    return sections.join('\n\n');
};

export { formatSoAIBenchHistoryMarkdown };

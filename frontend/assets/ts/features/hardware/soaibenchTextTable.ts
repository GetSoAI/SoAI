/* SoAI - SoAIBench text table formatting [frontend/assets/ts/features/hardware/soaibenchTextTable.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const escapeSoAIBenchTextTableCell = (value: string): string => {
    return value
        .replace(/\|/g, '\\|')
        .replace(/[\r\n]+/g, ' ')
        .trim();
};

const formatSoAIBenchTextTable = (headers: readonly string[], rows: readonly (readonly string[])[]): string => {
    if (headers.length === 0) {
        throw new Error('SoAIBench text table requires at least one column');
    }
    const escapedHeaders = headers.map(escapeSoAIBenchTextTableCell);
    const lines = [`| ${escapedHeaders.join(' | ')} |`, `| ${escapedHeaders.map(() => '---').join(' | ')} |`];
    for (const row of rows) {
        if (row.length !== headers.length) {
            throw new Error('SoAIBench text table rows must match the header width');
        }
        lines.push(`| ${row.map(escapeSoAIBenchTextTableCell).join(' | ')} |`);
    }
    return lines.join('\n');
};

export { escapeSoAIBenchTextTableCell, formatSoAIBenchTextTable };

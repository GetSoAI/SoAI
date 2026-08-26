/* SoAI - Frontend preinitialization bundle construction [frontend/scripts/preinitBundleBuilder.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname } from 'path';
import ts from 'typescript';

type PreinitFormatOutput = (output: string, outputPath: string) => Promise<string>;

interface PreinitBundleConfig {
    sourcePath: string;
    outputPath: string;
    outputHeaderTitle: string;
    outputRelativePath: string;
    emptyOutputMessage: string;
    formatOutput: PreinitFormatOutput;
}

const SPDX_LICENSE_LINE = '// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0';
const STRICT_MODE_DIRECTIVE = "'use strict';";

const ensureDirectory = (directoryPath: string): void => {
    mkdirSync(directoryPath, { recursive: true });
};

const readText = (filePath: string): string => {
    return readFileSync(filePath, 'utf-8');
};

const transpilePreinitSource = (sourceText: string, filename: string, emptyOutputMessage: string): string => {
    const result = ts.transpileModule(sourceText, {
        fileName: filename,
        compilerOptions: {
            target: ts.ScriptTarget.ES2020,
            module: ts.ModuleKind.None,
            strict: true,
            esModuleInterop: true
        },
        reportDiagnostics: true
    });

    const diagnostics = result.diagnostics ?? [];
    const errors = diagnostics.filter((diag) => diag.category === ts.DiagnosticCategory.Error);
    if (errors.length) {
        const host: ts.FormatDiagnosticsHost = {
            getCanonicalFileName: (filePath: string) => filePath,
            getCurrentDirectory: () => process.cwd(),
            getNewLine: () => '\n'
        };
        throw new Error(ts.formatDiagnosticsWithColorAndContext(errors, host));
    }

    const output = result.outputText;
    if (!output.trim()) {
        throw new Error(emptyOutputMessage);
    }
    return output;
};

const writeIfChanged = (filePath: string, next: string): void => {
    let current = '';
    try {
        current = readText(filePath);
    } catch (_readFailure) {
        current = '';
    }
    if (current !== next) {
        writeFileSync(filePath, next, 'utf-8');
    }
};

const stripInheritedPreamble = (transpiledText: string): string => {
    const lines = transpiledText.split('\n');
    let firstBodyLine = 0;
    while (firstBodyLine < lines.length) {
        const sourceLine = lines[firstBodyLine];
        if (sourceLine === undefined) {
            break;
        }
        const line = sourceLine.trim();
        const isStrictDirective = line === STRICT_MODE_DIRECTIVE || line === '"use strict";';
        const isInheritedBanner = line.startsWith('/*') && line.endsWith('*/');
        if (line === '' || isStrictDirective || isInheritedBanner || line === SPDX_LICENSE_LINE) {
            firstBodyLine += 1;
            continue;
        }
        break;
    }
    return lines.slice(firstBodyLine).join('\n');
};

const buildPreinitBundle = async (config: PreinitBundleConfig): Promise<void> => {
    const source = readText(config.sourcePath);
    const transpiledText = transpilePreinitSource(source, config.sourcePath, config.emptyOutputMessage);
    const bodyText = stripInheritedPreamble(transpiledText);
    const formattedBody = await config.formatOutput(bodyText, config.outputPath);
    const headedOutput = [`/* ${config.outputHeaderTitle} [${config.outputRelativePath}] */`, SPDX_LICENSE_LINE, '', STRICT_MODE_DIRECTIVE, formattedBody.replace(/^\n+/, '')].join('\n');
    ensureDirectory(dirname(config.outputPath));
    writeIfChanged(config.outputPath, headedOutput);
};

export { buildPreinitBundle };
export type { PreinitBundleConfig, PreinitFormatOutput };

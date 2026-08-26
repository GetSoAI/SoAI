#!/usr/bin/env node
/* SoAI - Frontend static icon registry generator [frontend/scripts/generateIconRegistry.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import prettier from 'prettier';
import { normalizeSvgMarkup } from '../assets/ts/core/ui/icons/iconMarkup.ts';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const iconsDir = path.join(projectRoot, 'assets', 'img', 'icons');
const outputPath = path.join(projectRoot, 'assets', 'ts', 'core', 'ui', 'icons', 'iconRegistry.generated.ts');
const svgExtensionPattern = /\.svg$/iu;

const readIconFileNames = (): readonly string[] =>
    fs
        .readdirSync(iconsDir, { withFileTypes: true })
        .filter((entry): entry is fs.Dirent => entry.isFile() && entry.name.endsWith('.svg'))
        .map((entry) => entry.name)
        .sort((a, b) => a.localeCompare(b));

const serializeIcon = (fileName: string): string => {
    const iconContent = normalizeSvgMarkup(fs.readFileSync(path.join(iconsDir, fileName), 'utf8'));
    return JSON.stringify(iconContent);
};

const buildIconLine = (fileName: string): string => {
    const baseName = fileName.replace(svgExtensionPattern, '');
    return `    ${JSON.stringify(baseName)}: ${serializeIcon(fileName)},`;
};

const buildFile = (fileNames: readonly string[]): string => {
    const header = '/* SoAI - Frontend core ui generated icon registry definitions [frontend/assets/ts/core/ui/icons/iconRegistry.generated.ts] */';
    const lines: string[] = [header, '// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0', '', 'export const STATIC_ICON_REGISTRY: Readonly<Record<string, string>> = {', ...fileNames.map(buildIconLine), '};', 'export type IconName = keyof typeof STATIC_ICON_REGISTRY;'];
    return `${lines.join('\n')}\n`;
};

const formatFile = async (source: string): Promise<string> => {
    const config = await prettier.resolveConfig(outputPath);
    return prettier.format(source, {
        ...(config ?? {}),
        filepath: outputPath
    });
};

const main = async (): Promise<void> => {
    const iconFileNames = readIconFileNames();
    const source = buildFile(iconFileNames);
    const formattedSource = await formatFile(source);
    fs.writeFileSync(outputPath, formattedSource, 'utf8');
};

const isDirectExecution = (): boolean => {
    const entryPath = process.argv[1];
    if (!entryPath) {
        return false;
    }
    return path.resolve(entryPath) === fileURLToPath(import.meta.url);
};

if (isDirectExecution()) {
    void main();
}

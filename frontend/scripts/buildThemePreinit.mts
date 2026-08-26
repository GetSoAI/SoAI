/* SoAI - Theme preinitialization bundle generation [frontend/scripts/buildThemePreinit.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { format, resolveConfig } from 'prettier';
import { buildPreinitBundle } from './preinitBundleBuilder.mts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourcePath = resolve(__dirname, '../assets/ts/critical/themePreinit.ts');
const outputPath = resolve(__dirname, '../assets/js/theme-preinit.js');

const formatOutput = async (output: string): Promise<string> => {
    const config = await resolveConfig(outputPath);
    if (!config) {
        throw new Error('Theme preinit formatter config is missing');
    }
    return format(output, { ...config, parser: 'babel' });
};

void buildPreinitBundle({
    sourcePath,
    outputPath,
    outputHeaderTitle: 'SoAI - Critical frontend theme preinitialization',
    outputRelativePath: 'frontend/assets/js/theme-preinit.js',
    emptyOutputMessage: 'Theme preinit output is empty',
    formatOutput
});

/* SoAI - Wallpaper preinitialization bundle generation [frontend/scripts/buildWallpaperPreinit.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { format, resolveConfig } from 'prettier';
import { buildPreinitBundle } from './preinitBundleBuilder.mts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourcePath = resolve(__dirname, '../assets/ts/critical/wallpaperPreinit.ts');
const outputPath = resolve(__dirname, '../assets/js/wallpaper-preinit.js');

const formatOutput = async (output: string): Promise<string> => {
    const config = await resolveConfig(outputPath);
    if (!config) {
        throw new Error('Wallpaper preinit formatter config is missing');
    }
    return format(output, { ...config, parser: 'babel' });
};

void buildPreinitBundle({
    sourcePath,
    outputPath,
    outputHeaderTitle: 'SoAI - Critical frontend wallpaper preinitialization',
    outputRelativePath: 'frontend/assets/js/wallpaper-preinit.js',
    emptyOutputMessage: 'Wallpaper preinit output is empty',
    formatOutput
});

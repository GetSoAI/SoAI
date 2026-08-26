/* SoAI - Catalog feature plugin assets [frontend/assets/ts/features/catalog/pluginAssets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

const BUILTIN_PLUGIN_LOGO_PATHS: Readonly<Record<string, string>> = Object.freeze({
    ollama: 'img/logo/ollama-plugin-logo.png',
    vllm: 'img/logo/vllm-plugin-logo.png',
    llamacpp: 'img/logo/llamacpp-plugin-logo.png',
    external: 'img/logo/external-plugin-logo.png',
    ctranslate2: 'img/logo/ctranslate2-plugin-logo.png',
    embedding: 'img/logo/embedding-plugin-logo.png',
    melotts: 'img/logo/melotts-plugin-logo.png',
    whisper: 'img/logo/whisper-plugin-logo.png'
});

const getPluginLogoPath = (plugin: PluginRecord | null | undefined): string => {
    if (!plugin) return '';
    const normalizedName = typeof plugin.name === 'string' ? plugin.name.trim().toLowerCase() : '';
    if (plugin.isBuiltin === true && normalizedName) {
        const builtinLogoPath = BUILTIN_PLUGIN_LOGO_PATHS[normalizedName];
        if (builtinLogoPath) {
            return resolveAssetPath(builtinLogoPath);
        }
    }
    return resolveAssetPath('img/logo/third-party-plugin-logo.png');
};

export { getPluginLogoPath };

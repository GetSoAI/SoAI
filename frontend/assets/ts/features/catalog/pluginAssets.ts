/* SoAI - Catalog feature plugin assets [frontend/assets/ts/features/catalog/pluginAssets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { pluginLogoPath } from '@core/api/endpoints/uiPaths.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

const ARCHIVE_REVISION_PATTERN = /^[a-f0-9]{64}$/;

interface PluginLogoPresentation {
    source: string;
    fallback: string;
}

const getPluginFallbackLogoPath = (plugin: PluginRecord | null | undefined): string => {
    if (!plugin) return '';
    return resolveAssetPath('img/logo/third-party-plugin-logo.png');
};

const getPluginArchiveLogoPath = (plugin: PluginRecord | null | undefined): string => {
    const pluginName = typeof plugin?.name === 'string' ? plugin.name.trim() : '';
    const revision = typeof plugin?.logoRevision === 'string' ? plugin.logoRevision.trim() : '';
    if (!pluginName || !ARCHIVE_REVISION_PATTERN.test(revision)) return '';
    return pluginLogoPath(pluginName, revision);
};

const getPluginLogoPresentation = (plugin: PluginRecord | null | undefined, fallbackOverride?: string): PluginLogoPresentation => {
    const fallback = fallbackOverride || getPluginFallbackLogoPath(plugin);
    return { source: getPluginArchiveLogoPath(plugin) || fallback, fallback };
};

const getPluginLogoPath = (plugin: PluginRecord | null | undefined): string => getPluginLogoPresentation(plugin).source;

export { getPluginArchiveLogoPath, getPluginFallbackLogoPath, getPluginLogoPath, getPluginLogoPresentation };
export type { PluginLogoPresentation };

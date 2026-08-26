/* SoAI - Plugins page collection grouping presentation [frontend/assets/ts/pages/plugins/controllers/page/pluginsGroupingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionGroupingState, CollectionGroupResolution } from '@core/collectionpage/collectionGroupingState.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { resolveAlphabeticGroupKey } from '@core/primitives/grouping.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

interface PluginsGroupingControllerDependencies {
    grouping: CollectionGroupingState<PluginRecord>;
    getSortBy: () => string;
    getItemCardId: (plugin: PluginRecord) => string | null;
    getPluginStatus: (plugin: PluginRecord) => string;
    getStatusDescription: (status: string) => string;
}

const resolveNameGroup = (plugin: PluginRecord): CollectionGroupResolution => {
    const heading = resolveAlphabeticGroupKey(toTrimmedString(plugin.displayName) || toTrimmedString(plugin.name));
    return { key: heading, heading };
};

const resolveModelCountGroup = (plugin: PluginRecord): CollectionGroupResolution => {
    const count = plugin.stats?.modelCount ?? 0;
    if (count <= 0) return { key: 'none', heading: i18n.t('plugins.groups.models.none') };
    if (count === 1) return { key: 'one', heading: i18n.t('plugins.groups.models.one') };
    if (count <= 4) return { key: 'twoToFour', heading: i18n.t('plugins.groups.models.twoToFour') };
    if (count <= 9) return { key: 'fiveToNine', heading: i18n.t('plugins.groups.models.fiveToNine') };
    return { key: 'tenOrMore', heading: i18n.t('plugins.groups.models.tenOrMore') };
};

const createPluginsGroupingController = (dependencies: PluginsGroupingControllerDependencies) => {
    const resolveGroup = (plugin: PluginRecord, sortBy: string): CollectionGroupResolution => {
        if (sortBy === 'name') return resolveNameGroup(plugin);
        if (sortBy === 'models') return resolveModelCountGroup(plugin);
        if (sortBy === 'status') {
            const status = dependencies.getPluginStatus(plugin);
            return status ? { key: status, heading: dependencies.getStatusDescription(status) } : { key: null, heading: null };
        }
        return { key: null, heading: null };
    };

    const preparePresentation = (plugins: readonly PluginRecord[]): string[] => {
        const sortBy = dependencies.getSortBy();
        return dependencies.grouping.applyHeadings({
            items: plugins,
            grouped: sortBy !== 'none',
            resolveItemId: (plugin) => dependencies.getItemCardId(plugin) ?? '',
            resolveGroup: (plugin) => resolveGroup(plugin, sortBy)
        });
    };

    return { preparePresentation };
};

export { createPluginsGroupingController };
export type { PluginsGroupingControllerDependencies };

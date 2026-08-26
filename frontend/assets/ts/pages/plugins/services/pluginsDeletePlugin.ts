/* SoAI - Plugins page delete plugin [frontend/assets/ts/pages/plugins/services/pluginsDeletePlugin.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { pluginDeletePath } from '@core/api/endpoints/uiPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { CollectionRuntime, StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { PLUGIN_CARD_SELECTOR, PLUGINS_GRID, type ExecuteItemDeletionOptions } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';

interface PluginsDeletePluginHost extends PageDomOwnerHost {
    deletingItems: Set<string>;
    getCollectionRuntime(): CollectionRuntime | null;
    getCatalogPlugin(identifier: string): PluginRecord | null;
    sanitizeText(value: JsonValue): string;
    startDeleteStream(identifier: string, displayName: string): Promise<StreamActionHandle>;
    beginOptimisticOperation(operation: OptimisticOperation): void;
}

const resolveDisplayName = (host: PluginsDeletePluginHost, identifier: string, lookup: ResourceItem | PluginRecord | null): string => {
    const displayNameCandidate = lookup && isObject(lookup) ? (isString(lookup.displayName) ? lookup.displayName : isString(lookup.name) ? lookup.name : null) : null;
    return host.sanitizeText(displayNameCandidate ?? identifier);
};

const resolveCollectionLookup = (collection: CollectionRuntime | null, identifier: string): ResourceItem | null => {
    if (!collection) {
        return null;
    }
    const findByIdentifier = collection.find(identifier);
    if (findByIdentifier) {
        return findByIdentifier;
    }
    return collection.find(identifier.toLowerCase());
};

const buildDeleteOptions = (host: PluginsDeletePluginHost, pluginName: string): ExecuteItemDeletionOptions | null => {
    const identifier = toTrimmedString(pluginName);
    if (!identifier || host.deletingItems.has(identifier)) {
        return null;
    }

    const collection = host.getCollectionRuntime();
    const lookup = resolveCollectionLookup(collection, identifier) || host.getCatalogPlugin(identifier) || null;
    const displayName = resolveDisplayName(host, identifier, lookup);
    if (!displayName) {
        throw new Error(`Plugin deletion requires a valid identifier: ${identifier}`);
    }

    return {
        identifier,
        confirmTitle: i18n.t('plugins.confirmations.deletePlugin'),
        confirmMessage: i18n.t('plugins.confirmations.deleteMessage', { plugin: displayName }),
        confirmButton: i18n.t('plugins.confirmations.deleteButton'),
        getStream: () => host.startDeleteStream(identifier, displayName),
        gridSelector: PLUGINS_GRID.gridId,
        findCard: (grid: HTMLElement | null, id: string): HTMLElement | null => {
            const candidate = host.pageDom.optional(`${PLUGIN_CARD_SELECTOR}[data-plugin="${id}"]`, grid ?? undefined);
            return candidate instanceof HTMLElement ? candidate : null;
        },
        pendingClass: 'pending-delete',
        successMessage: i18n.t('plugins.notifications.deleteSuccess', { plugin: displayName }),
        onAccepted: (taskId): void => {
            host.beginOptimisticOperation({
                operationId: taskId,
                itemId: identifier,
                desiredItem: null,
                acceptedTaskId: taskId
            });
        },
        projectLocally: false
    };
};

export const deletePluginWithStream = async (host: PluginsDeletePluginHost, pluginName: string, executeItemDeletion: (options: ExecuteItemDeletionOptions) => Promise<void>): Promise<void> => {
    const options = buildDeleteOptions(host, pluginName);
    if (!options) {
        return;
    }
    await executeItemDeletion(options);
};

type CreatePluginDeleteStreamStarterDependencies = {
    startTaskAction: (endpoint: string, options: { method: string; operation: JsonObject }) => Promise<StreamActionHandle>;
};

export const createPluginDeleteStreamStarter = (dependencies: CreatePluginDeleteStreamStarterDependencies): ((identifier: string, displayName: string) => Promise<StreamActionHandle>) => {
    return (identifier: string, displayName: string): Promise<StreamActionHandle> =>
        dependencies.startTaskAction(pluginDeletePath(identifier), {
            method: 'DELETE',
            operation: {
                type: 'plugin-delete',
                plugin: identifier,
                pluginName: identifier,
                displayName,
                cancelable: false
            }
        });
};

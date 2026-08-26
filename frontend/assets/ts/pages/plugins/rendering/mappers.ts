/* SoAI - Plugins page rendering layer mapping [frontend/assets/ts/pages/plugins/rendering/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { pluginsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { buildCardGridHeader, buildCollectionSections, buildEmptyState } from '@core/routing/pages/collections/collectionViewBuilders.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { renderListTable, type ListTableColumn } from '@core/uiprimitives/listTable.ts';
import { renderSortControl } from '@core/uiprimitives/sortableList.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import { PLUGINS_ACTION_DOWNLOAD_PLUGIN, PLUGINS_ACTION_OPEN_CONCURRENT, PLUGINS_ACTION_STOP_ALL } from '@features/plugins/public.ts';
import { PLUGINS_ACTION_SORT_LIST, PLUGINS_ACTION_TOGGLE_VIEW_MODE } from '@pages/plugins/actions.ts';
import { createPluginsSortControlDefinition, normalizePluginsSortState } from '@pages/plugins/controllers/page/listSortingController.ts';
import type { GetIconSyncFunctionValue } from '@pages/plugins/rendering/contracts.ts';

const PLUGINS_GRID = pluginsPageConfig.grid;
const PLUGIN_EMPTY_STATES = PLUGINS_GRID.emptyStateIds;

const buildPluginsHeader = (getIconSync: GetIconSyncFunctionValue, sortBy: string, sortOrder: SortDirection) => {
    return buildCardGridHeader({
        title: i18n.t('plugins.title'),
        description: i18n.t('plugins.description'),
        actions: [
            { type: 'search' },
            { type: 'custom', html: renderSortControl(createPluginsSortControlDefinition(normalizePluginsSortState({ sortBy, sortOrder }))) },
            {
                type: 'filter',
                filter: {
                    type: 'select',
                    id: 'provider-filter',
                    options: [
                        { value: 'all', label: i18n.t('plugins.filters.allPlugins') },
                        { value: 'active', label: i18n.t('plugins.filters.active') },
                        { value: 'inactive', label: i18n.t('plugins.filters.inactive') }
                    ]
                }
            },
            {
                type: 'filter',
                filter: {
                    type: 'select',
                    id: 'status-filter',
                    options: [
                        { value: 'all', label: i18n.t('plugins.filters.allTypes') },
                        { value: 'builtin', label: i18n.t('plugins.filters.builtin') },
                        { value: 'thirdparty', label: i18n.t('plugins.filters.thirdparty') }
                    ]
                }
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('stop', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('plugins.actions.stopAllPlugins')}</span>`,
                variant: 'ui-variant-danger',
                id: PLUGINS_ACTION_STOP_ALL,
                attributes: { 'data-action': PLUGINS_ACTION_STOP_ALL },
                ariaLabel: i18n.t('plugins.actions.stopAllPlugins')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('dashboard', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('common.actions.cardView')}</span>`,
                variant: 'ui-variant-neutral',
                id: 'plugins-view-mode-toggle',
                attributes: { 'data-action': PLUGINS_ACTION_TOGGLE_VIEW_MODE, 'aria-pressed': 'false' },
                ariaLabel: i18n.t('common.actions.cardView')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('add', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('plugins.actions.installPlugin')}</span>`,
                variant: 'ui-variant-accent',
                id: PLUGINS_ACTION_DOWNLOAD_PLUGIN,
                attributes: { 'data-action': PLUGINS_ACTION_DOWNLOAD_PLUGIN },
                ariaLabel: i18n.t('plugins.actions.installPlugin')
            }
        ],
        stats: [
            { id: 'total-plugins', label: i18n.t('plugins.stats.totalPlugins.plural') },
            { id: 'active-plugins', label: i18n.t('plugins.stats.activePlugins.plural') },
            { id: 'persistent-plugins', label: i18n.t('plugins.stats.persistentPlugins.plural') },
            {
                id: 'max-concurrent-plugins',
                label: i18n.t('plugins.stats.concurrentPlugins.plural'),
                actions: [{ actionId: PLUGINS_ACTION_OPEN_CONCURRENT, label: i18n.t('plugins.actions.configureConcurrentPlugins') }]
            },
            { id: 'last-used-plugin', label: i18n.t('plugins.stats.lastUsedPlugin') }
        ]
    });
};

const buildPluginsListColumns = (sortBy: string, sortOrder: SortDirection): readonly ListTableColumn[] => [
    { label: i18n.t('plugins.table.plugin'), sortKey: 'name', sortAction: PLUGINS_ACTION_SORT_LIST, active: sortBy === 'name', direction: sortBy === 'name' ? sortOrder : undefined },
    { label: i18n.t('plugins.badges.models'), sortKey: 'models', sortAction: PLUGINS_ACTION_SORT_LIST, active: sortBy === 'models', direction: sortBy === 'models' ? sortOrder : undefined },
    { label: i18n.t('plugins.table.status'), sortKey: 'status', sortAction: PLUGINS_ACTION_SORT_LIST, active: sortBy === 'status', direction: sortBy === 'status' ? sortOrder : undefined },
    { label: i18n.t('common.actions.actions'), className: 'ui-collection-list__header-cell--actions' }
];

const buildPluginsSections = (sortBy: string, sortOrder: SortDirection) => {
    const sections = buildCollectionSections({
        gridId: PLUGINS_GRID.gridId,
        gridClassName: PLUGINS_GRID.gridClassName,
        emptyStates: [
            buildEmptyState({
                id: PLUGIN_EMPTY_STATES.empty,
                className: 'plugins-empty ui-collection-list__empty-state',
                icon: { name: 'search', options: { size: 48, strokeWidth: 1.5 } },
                title: i18n.t('plugins.empty.noPlugins'),
                description: i18n.t('plugins.empty.noMatch')
            })
        ]
    });
    sections.splice(1, 0, {
        type: 'section',
        tag: 'div',
        id: 'plugins-list-surface',
        className: 'plugins-list-surface ui-collection-list',
        role: 'region',
        children: renderListTable({ tableClassName: 'plugins-list-table', bodyId: 'plugins-list-body', columns: buildPluginsListColumns(sortBy, sortOrder) })
    });
    return sections;
};

export { buildPluginsHeader, buildPluginsSections };

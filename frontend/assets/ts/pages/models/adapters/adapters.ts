/* SoAI - Models page adapters implementation [frontend/assets/ts/pages/models/adapters/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { buildCardGridHeader, buildCollectionSections, buildEmptyState } from '@core/routing/pages/collections/collectionViewBuilders.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { renderListTable, type ListTableColumn } from '@core/uiprimitives/listTable.ts';
import { renderSortControl } from '@core/uiprimitives/sortableList.ts';
import { MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS, MODELS_ACTION_MANAGE_VIRTUAL_MODELS, MODELS_ACTION_OPEN_METRICS, MODELS_ACTION_OPEN_PROVIDER_TAB } from '@core/models/pageActions.ts';
import { MODELS_ACTION_SORT_LIST, MODELS_ACTION_TOGGLE_VIEW_MODE } from '@pages/models/actions.ts';
import { MODEL_EMPTY_STATES, MODELS_GRID } from '@pages/models/contracts/constants.ts';
import type { ModelsLayoutViewHost } from '@pages/models/types.ts';
import { createModelsSortControlDefinition, normalizeModelsSortState } from '@pages/models/controllers/page/listSortingController.ts';

const buildModelsHeader = (page: ModelsLayoutViewHost) => {
    return buildCardGridHeader({
        title: i18n.t('models.title'),
        description: i18n.t('models.description'),
        actions: [
            { type: 'search' },
            { type: 'custom', html: renderSortControl(createModelsSortControlDefinition(normalizeModelsSortState({ sortBy: page.sortBy, sortOrder: page.sortOrder }))) },
            {
                type: 'filter',
                filter: {
                    type: 'select',
                    id: 'provider-filter',
                    options: [{ value: 'all', label: i18n.t('models.filters.allPlugins') }]
                }
            },
            {
                type: 'button',
                content: uiHtml`${page.getIconSync('model-virtual', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('models.actions.virtualModelsButton')}</span>`,
                id: MODELS_ACTION_MANAGE_VIRTUAL_MODELS,
                attributes: { 'data-action': MODELS_ACTION_MANAGE_VIRTUAL_MODELS },
                ariaLabel: i18n.t('models.actions.manageVirtualModels')
            },
            {
                type: 'button',
                content: uiHtml`${page.getIconSync('provider', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('models.actions.providersButton')}</span>`,
                id: MODELS_ACTION_MANAGE_PROVIDERS,
                attributes: { 'data-action': MODELS_ACTION_MANAGE_PROVIDERS },
                ariaLabel: i18n.t('models.actions.manageProviders')
            },
            {
                type: 'button',
                content: uiHtml`${page.getIconSync('dashboard', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('common.actions.cardView')}</span>`,
                variant: 'ui-variant-neutral',
                id: 'models-view-mode-toggle',
                attributes: { 'data-action': MODELS_ACTION_TOGGLE_VIEW_MODE, 'aria-pressed': 'false' },
                ariaLabel: i18n.t('common.actions.cardView')
            },
            {
                type: 'button',
                content: uiHtml`${page.getIconSync('add', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('models.actions.addModel')}</span>`,
                variant: 'ui-variant-accent',
                id: MODELS_ACTION_DOWNLOAD_MODEL,
                attributes: { 'data-action': MODELS_ACTION_DOWNLOAD_MODEL },
                ariaLabel: i18n.t('models.actions.addModel')
            }
        ],
        stats: [
            { id: 'total-models', label: i18n.t('models.stats.totalModels.plural') },
            { id: 'local-models', label: i18n.t('models.stats.local_models.plural') },
            {
                id: 'virtual-models',
                label: i18n.t('models.stats.virtualModels.plural'),
                actions: [{ actionId: MODELS_ACTION_MANAGE_VIRTUAL_MODELS, label: i18n.t('models.actions.manageVirtualModels'), iconName: 'settings' }]
            },
            { id: 'loaded-models', label: i18n.t('models.stats.loaded.plural') },
            {
                id: 'external-models',
                label: i18n.t('models.stats.externalProviders.plural'),
                actions: [{ actionId: MODELS_ACTION_OPEN_PROVIDER_TAB, label: i18n.t('models.modal.addProvider.title'), iconName: 'settings' }]
            },
            {
                id: 'requests-total',
                label: i18n.t('models.stats.requests.plural'),
                actions: [{ actionId: MODELS_ACTION_OPEN_METRICS, label: i18n.t('models.actions.viewMetrics'), iconName: 'dot' }]
            },
            { id: 'last-used-model', label: i18n.t('models.stats.lastUsedModel') },
            { id: 'total-size', label: i18n.t('models.stats.totalSize') }
        ]
    });
};

const buildModelsListColumns = (page: Pick<ModelsLayoutViewHost, 'sortBy' | 'sortOrder'>): readonly ListTableColumn[] => [
    { label: i18n.t('models.table.model'), sortKey: 'name', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'name', direction: page.sortBy === 'name' ? page.sortOrder : undefined },
    { label: i18n.t('models.table.type'), sortKey: 'type', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'type', direction: page.sortBy === 'type' ? page.sortOrder : undefined },
    { label: i18n.t('models.table.provider'), sortKey: 'provider', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'provider', direction: page.sortBy === 'provider' ? page.sortOrder : undefined },
    { label: i18n.t('models.sort.byPlugin'), sortKey: 'plugin', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'plugin', direction: page.sortBy === 'plugin' ? page.sortOrder : undefined },
    { label: i18n.t('models.table.metrics'), sortKey: 'size', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'size', direction: page.sortBy === 'size' ? page.sortOrder : undefined },
    { label: i18n.t('models.table.status'), sortKey: 'status', sortAction: MODELS_ACTION_SORT_LIST, active: page.sortBy === 'status', direction: page.sortBy === 'status' ? page.sortOrder : undefined },
    { label: i18n.t('common.actions.actions'), className: 'ui-collection-list__header-cell--actions' }
];

const buildModelsSections = (page: Pick<ModelsLayoutViewHost, 'sortBy' | 'sortOrder'>) => {
    const sections = buildCollectionSections({
        gridId: MODELS_GRID.gridId,
        gridClassName: MODELS_GRID.gridClassName,
        emptyStates: [
            buildEmptyState({
                id: MODEL_EMPTY_STATES.empty,
                className: 'models-empty ui-collection-list__empty-state',
                icon: { name: 'search', options: { size: 48, strokeWidth: 1.5 } },
                title: i18n.t('models.empty.noModels'),
                description: i18n.t('models.empty.getStarted'),
                body: `<button type="button" class="ui-button ui-variant-accent u-hidden" id="${MODEL_EMPTY_STATES.firstDownload}" data-action="${MODELS_ACTION_DOWNLOAD_MODEL}" ${renderLabelAttributes(i18n.t('models.empty.downloadFirst'))}>${i18n.t('models.empty.downloadFirst')}</button>`
            }),
            buildEmptyState({
                id: MODEL_EMPTY_STATES.filtered ?? '',
                className: 'models-filtered-empty ui-collection-list__empty-state',
                icon: { name: 'search', options: { size: 48, strokeWidth: 1.5 } },
                title: i18n.t('models.empty.noMatch'),
                description: i18n.t('models.empty.tryAdjusting')
            })
        ]
    });
    sections.splice(1, 0, {
        type: 'section',
        tag: 'div',
        id: 'models-list-surface',
        className: 'models-list-surface ui-collection-list',
        role: 'region',
        children: renderListTable({ tableClassName: 'models-list-table', bodyId: 'models-list-body', columns: buildModelsListColumns(page) })
    });
    return sections;
};

const buildModelsFilters = (): { '#provider-filter': string } => {
    return {
        '#provider-filter': 'filterProvider'
    };
};

export { buildModelsHeader, buildModelsFilters, buildModelsSections };

/* SoAI - Shared collection page routing configuration [frontend/assets/ts/core/routing/pages/collections/collectionPageConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface EmptyStateIds {
    empty: string;
    filtered?: string | undefined;
    firstDownload?: string | undefined;
}

interface GridConfig {
    gridId: string;
    gridSelector: string;
    gridClassName: string;
    cardSelector: string;
    emptyStateIds: Readonly<EmptyStateIds>;
}

interface CollectionPageConfig {
    dataKey: string;
    itemLabel: string;
    collectionName: string;
    grid: Readonly<GridConfig>;
}

const modelsPageConfig: Readonly<CollectionPageConfig> = Object.freeze({
    dataKey: 'model',
    itemLabel: 'Model',
    collectionName: 'models',
    grid: Object.freeze({
        gridId: 'models-grid',
        gridSelector: '#models-grid',
        gridClassName: 'ui-collection-grid models-grid',
        cardSelector: '.model-card',
        emptyStateIds: Object.freeze({
            empty: 'models-empty',
            filtered: 'models-filtered-empty',
            firstDownload: 'download-first-model'
        })
    })
});

const pluginsPageConfig: Readonly<CollectionPageConfig> = Object.freeze({
    dataKey: 'plugin',
    itemLabel: 'Plugin',
    collectionName: 'plugins',
    grid: Object.freeze({
        gridId: 'plugins-grid',
        gridSelector: '#plugins-grid',
        gridClassName: 'ui-collection-grid plugins-grid',
        cardSelector: '.plugin-card',
        emptyStateIds: Object.freeze({
            empty: 'plugins-empty'
        })
    })
});

const promptsPageConfig: Readonly<CollectionPageConfig> = Object.freeze({
    dataKey: 'prompt',
    itemLabel: 'Prompt',
    collectionName: 'prompts',
    grid: Object.freeze({
        gridId: 'prompts-grid',
        gridSelector: '#prompts-grid',
        gridClassName: 'ui-collection-grid prompts-grid',
        cardSelector: '.prompt-card',
        emptyStateIds: Object.freeze({
            empty: 'prompts-empty',
            filtered: 'prompts-filtered-empty'
        })
    })
});

export { modelsPageConfig, pluginsPageConfig, promptsPageConfig };
export type { EmptyStateIds, GridConfig, CollectionPageConfig };

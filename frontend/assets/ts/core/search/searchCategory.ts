/* SoAI - Search category normalization [frontend/assets/ts/core/search/searchCategory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isString } from '@core/typeGuards.ts';

type SearchFilter = 'all' | 'models' | 'plugins' | 'hardware' | 'files' | 'conversations' | 'prompts' | 'pages' | 'config' | 'configuration' | 'help' | 'modals' | 'power-actions' | 'recent';
type SearchVisibleTab = 'all' | 'models' | 'plugins' | 'hardware' | 'files' | 'conversations' | 'prompts' | 'configuration' | 'help' | 'modals' | 'power-actions' | 'recent';

interface SearchTabCounts {
    all: number;
    models: number;
    plugins: number;
    hardware: number;
    files: number;
    conversations: number;
    prompts: number;
    configuration: number;
    help: number;
    modals: number;
    'power-actions': number;
    recent: number;
}

const SEARCH_VISIBLE_TAB_IDS: readonly SearchVisibleTab[] = Object.freeze(['all', 'models', 'plugins', 'hardware', 'files', 'conversations', 'prompts', 'configuration', 'help', 'modals', 'power-actions', 'recent']);

const normalizeSearchFilter = (value: string | null | undefined): SearchFilter | null => {
    if (!isString(value)) {
        return null;
    }
    switch (toTrimmedLower(value)) {
        case 'all':
            return 'all';
        case 'models':
            return 'models';
        case 'plugins':
            return 'plugins';
        case 'hardware':
            return 'hardware';
        case 'files':
            return 'files';
        case 'conversations':
            return 'conversations';
        case 'prompts':
            return 'prompts';
        case 'pages':
            return 'pages';
        case 'config':
            return 'config';
        case 'configuration':
            return 'configuration';
        case 'help':
            return 'help';
        case 'modal':
        case 'modals':
            return 'modals';
        case 'power-actions':
            return 'power-actions';
        case 'recent':
            return 'recent';
        default:
            return null;
    }
};

const normalizeSearchCategory = (category: string): string => {
    const normalized = toTrimmedLower(category);
    switch (normalized) {
        case 'models':
            return 'model';
        case 'plugins':
            return 'plugin';
        case 'devices':
            return 'device';
        case 'pages':
            return 'page';
        case 'file':
        case 'directory':
        case 'folders':
        case 'folder':
            return 'files';
        case 'conversation':
            return 'conversation';
        case 'conversations':
            return 'conversation';
        case 'prompt':
            return 'prompt';
        case 'prompts':
            return 'prompt';
        case 'modals':
            return 'modal';
        case 'poweractions':
            return 'power-actions';
        default:
            return normalized;
    }
};

const resolveSearchCategoryLabel = (category: string): string => {
    const normalized = normalizeSearchCategory(category);
    switch (normalized) {
        case 'model':
        case 'virtual':
            return i18n.t('search.categories.models');
        case 'plugin':
            return i18n.t('search.categories.plugins');
        case 'device':
        case 'hardware':
            return i18n.t('search.categories.hardware');
        case 'config':
        case 'configuration':
            return i18n.t('search.categories.configuration');
        case 'page':
            return i18n.t('search.categories.pages');
        case 'files':
            return i18n.t('search.categories.files');
        case 'conversation':
            return i18n.t('search.categories.conversations');
        case 'prompt':
            return i18n.t('search.categories.prompts');
        case 'help':
            return i18n.t('search.categories.help');
        case 'modal':
            return i18n.t('search.categories.modals');
        case 'power-actions':
            return i18n.t('search.categories.powerActions');
    }
    throw new Error(`Unsupported search category "${normalized}"`);
};

const resolveSearchTabLabel = (tab: SearchVisibleTab): string => {
    switch (tab) {
        case 'all':
            return i18n.t('search.tabs.all');
        case 'models':
            return i18n.t('search.tabs.models');
        case 'plugins':
            return i18n.t('search.tabs.plugins');
        case 'hardware':
            return i18n.t('search.tabs.hardware');
        case 'files':
            return i18n.t('search.tabs.files');
        case 'conversations':
            return i18n.t('search.tabs.conversations');
        case 'prompts':
            return i18n.t('search.tabs.prompts');
        case 'configuration':
            return i18n.t('search.tabs.configuration');
        case 'help':
            return i18n.t('search.tabs.help');
        case 'modals':
            return i18n.t('search.tabs.modals');
        case 'power-actions':
            return i18n.t('search.tabs.powerActions');
        case 'recent':
            return i18n.t('search.tabs.recent');
    }
};

const resolveSearchCategoryFilter = (category: string): SearchFilter | null => {
    const normalized = normalizeSearchCategory(category);
    switch (normalized) {
        case 'model':
        case 'virtual':
            return 'models';
        case 'plugin':
            return 'plugins';
        case 'device':
        case 'hardware':
            return 'hardware';
        case 'page':
            return 'pages';
        case 'config':
        case 'configuration':
            return 'configuration';
        case 'files':
            return 'files';
        case 'conversation':
            return 'conversations';
        case 'prompt':
            return 'prompts';
        case 'help':
            return 'help';
        case 'modal':
            return 'modals';
        case 'power-actions':
            return 'power-actions';
        default:
            return null;
    }
};

const searchCategoryMatchesFilter = (category: string, filter: SearchFilter): boolean => {
    if (filter === 'all') {
        return true;
    }
    if (filter === 'recent') {
        return false;
    }
    const categoryFilter = resolveSearchCategoryFilter(category);
    if (filter === 'config') {
        return categoryFilter === 'configuration';
    }
    return categoryFilter === filter;
};

const countSearchResultsByTab = (results: readonly SearchItem[], recentCount: number): SearchTabCounts => {
    let models = 0;
    let plugins = 0;
    let hardware = 0;
    let files = 0;
    let conversations = 0;
    let prompts = 0;
    let configuration = 0;
    let help = 0;
    let modals = 0;
    let powerActions = 0;
    for (const item of results) {
        const filter = resolveSearchCategoryFilter(item.type);
        if (filter === 'models') {
            models += 1;
        } else if (filter === 'plugins') {
            plugins += 1;
        } else if (filter === 'hardware') {
            hardware += 1;
        } else if (filter === 'files') {
            files += 1;
        } else if (filter === 'conversations') {
            conversations += 1;
        } else if (filter === 'prompts') {
            prompts += 1;
        } else if (filter === 'configuration') {
            configuration += 1;
        } else if (filter === 'help') {
            help += 1;
        } else if (filter === 'modals') {
            modals += 1;
        } else if (filter === 'power-actions') {
            powerActions += 1;
        }
    }
    return {
        all: results.length,
        models,
        plugins,
        hardware,
        files,
        conversations,
        prompts,
        configuration,
        help,
        modals,
        'power-actions': powerActions,
        recent: recentCount
    };
};

export { SEARCH_VISIBLE_TAB_IDS, countSearchResultsByTab, normalizeSearchCategory, normalizeSearchFilter, resolveSearchCategoryFilter, resolveSearchCategoryLabel, resolveSearchTabLabel, searchCategoryMatchesFilter };
export type { SearchFilter, SearchTabCounts };

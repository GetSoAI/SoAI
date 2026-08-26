/* SoAI - Search page services contracts [frontend/assets/ts/pages/search/services/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchFilter, SearchTabCounts } from '@core/search/searchCategory.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { SearchDataController } from '@pages/search/controllers/dataController.ts';
import type { SearchRenderController } from '@pages/search/controllers/renderController.ts';
import type { SearchUiRefs } from '@pages/search/types.ts';

interface SearchHistoryDependencies {
    getRecentSearches: () => string[];
    addRecentSearch: (query: string) => void;
    clearRecentSearches: () => void;
}

interface SearchViewDependencies {
    getUiRefs: () => SearchUiRefs;
    setLoadingState: (element: HTMLElement, isLoading: boolean, statusMessage?: string) => void;
    toggleResultsVisibility: (show: boolean) => void;
    updateHTML: (element: HTMLElement, html: TrustedHtml, options?: { escape?: boolean }) => void;
    showStatusMessage: (title: string, message: string, clearBadges: boolean) => void;
    showInitializingMessage: () => void;
    updateTabNotifyBadges: (counts: SearchTabCounts) => void;
    clearTabNotifyBadges: () => void;
    setActiveTab: (tab: SearchFilter) => void;
    setSearchValue: (value: string) => void;
    setTabNotifyBadge: (tab: SearchFilter, count: number) => void;
}

interface SearchNavigationDependencies {
    navigate: (path: string) => void;
    navigateWithQuery: (path: string, query: Record<string, string>, options?: { force?: boolean }) => void;
    openFilePreview: (path: string) => Promise<boolean>;
    openPromptPreview: (promptId: string) => Promise<boolean>;
}

interface SearchErrorDependencies {
    reportError: (error: Error, options: { context?: string; userMessage?: string }) => void;
}

interface SearchPageServiceDependencies {
    dataController: SearchDataController;
    renderController: SearchRenderController;
    searchHistory: SearchHistoryDependencies;
    view: SearchViewDependencies;
    navigation: SearchNavigationDependencies;
    errors: SearchErrorDependencies;
}

export type { SearchErrorDependencies, SearchHistoryDependencies, SearchNavigationDependencies, SearchPageServiceDependencies, SearchViewDependencies };

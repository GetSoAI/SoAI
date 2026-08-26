/* SoAI - Shared layout search manager contracts [frontend/assets/ts/core/layout/header/searchmanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { HeaderEscapableValue, HeaderServiceResolver, IconOptions } from '@core/layout/HeaderInterface.ts';
import type { NavigationOptions } from '@core/routing/router/types.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

interface SearchIconsService {
    get: (name: string, options?: IconOptions) => TrustedHtml | undefined;
}

interface SearchStorageService {
    addRecentSearch: (query: string) => void;
}

export interface SearchManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getDom: (key: string) => HTMLElement | null;
    closeDropdowns: (options?: { except?: string | string[] | undefined }) => void;
    setTimer: (callback: () => void, delay: number, options?: { repeat?: boolean }) => number | null;
    clearTimer: (id: number | null) => void;
    removeClassName: (element: Element, className: string | string[]) => void;
    updateProperty: (element: HTMLElement, property: string, value: DomPropertyValue) => void;
    addClassName: (element: Element, className: string | string[]) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    updateHTML: (element: HTMLElement, html: TrustedHtml | string, options: { escape: boolean }) => void;
    resolveService: HeaderServiceResolver;
    escape: (value: HeaderEscapableValue) => string;
    logger: (level: string, message: string, data?: TelemetryValue) => void;
    getStorage: () => SearchStorageService;
    icons: SearchIconsService;
}

export interface SearchPanelInterface {
    initialize: () => Promise<void>;
    isInitialized?: boolean | undefined;
    search: (query: string, limit: number, options: { immediate: boolean; signal?: AbortSignal | null | undefined }) => Promise<SearchItem[]>;
    searchFiles: (query: string, limit: number, options?: { signal?: AbortSignal | null | undefined }) => Promise<SearchItem[]>;
    openPromptPreview: (promptId: string) => Promise<boolean>;
    isSystemReady?: () => boolean;
}

export interface SearchManagerOptions {
    header: SearchManagerHost;
}

export interface SearchManagerRefs {
    container: HTMLElement;
    input: HTMLInputElement;
    button: HTMLElement;
    dropdown: HTMLElement;
}

export interface SearchManagerCollapseOptions {
    blur?: boolean | undefined;
}

export interface SearchNavigationCommand {
    route: string;
    query?: Record<string, string>;
}

export interface RouterInterface {
    navigate: (route: string) => Promise<void>;
    navigateWithQuery: (route: string, query: Record<string, string>, options?: NavigationOptions) => void;
}

export interface StatusManagerInterface {
    createIndicator: (status: string) => HTMLElement;
}

export interface SearchManagerState {
    expanded: boolean;
    selectedIndex: number;
    timeoutId: number | null;
    blurTimeoutId: number | null;
    searchToken: number;
    panel: SearchPanelInterface | null;
    searchAbortController: AbortController | null;
}

export interface HeaderSearchManagerContract extends SearchManagerState {
    header: SearchManagerHost;
    statusManager: StatusManagerInterface;
    container: HTMLElement | null;
    input: HTMLInputElement | null;
    button: HTMLElement | null;
    dropdown: HTMLElement | null;

    requireDom: () => SearchManagerRefs;
    requireDropdownItems: () => HTMLElement[];

    advanceSearchToken: () => number;
    startSearchRequest: () => AbortController;
    abortSearchRequest: () => void;
    cancelScheduledSearch: () => void;
    cancelBlurTimer: () => void;
    isSessionActive: (token: number) => boolean;
    resetDropdown: () => void;
    resetResults: () => void;
    hideDropdown: () => void;
    collapse: (options?: SearchManagerCollapseOptions) => void;
    expand: () => void;
    localize: () => void;
    updateButtonIcon: () => void;
    handleResize: () => void;
    handleInput: () => void;
    handleKeyDown: (event: KeyboardEvent) => void;
    handleButtonClick: (event: Event) => void;

    scheduleSearch: (query: string, token?: number) => void;
    performSearch: (query: string, token?: number) => Promise<void>;

    displayResults: (results: SearchItem[]) => void;
    displayResultsWithCategoryState: (results: SearchItem[], state: { category: string; type: 'loading' | 'empty' | 'error'; message: string }) => void;
    displayNoResults: (query: string) => void;
    displaySearchInitializing: () => void;
    displaySearchError: () => void;
    showMessage: (markup: TrustedHtml) => void;

    updateSelectedItems: (nodes: HTMLElement[], options?: { scroll?: boolean }) => void;
    navigateSearchItem: (nodes: HTMLElement[], delta: number) => void;
}

export type { SearchItem, SearchIconsService, SearchStorageService };

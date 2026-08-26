/* SoAI - Search page boundary contracts [frontend/assets/ts/pages/search/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchItem, SearchOptions, TypeMetadata } from '@core/search/searchTypes.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';

export interface SearchPageDependencies {
    searchComponent: SearchComponentContract;
}

export interface SearchStatusIndicatorFactory {
    createIndicator?: (status: string) => HTMLElement;
}

export interface SearchComponentContract {
    isInitialized: boolean;
    initialize(): Promise<void>;
    search(query: string, limit: number, options?: SearchOptions): Promise<SearchItem[]>;
    searchFiles(query: string, limit: number, options?: SearchOptions): Promise<SearchItem[]>;
    openPromptPreview(promptId: string): Promise<boolean>;
    isSystemReady?: (() => boolean) | undefined;
    getTypeMetadata(category: string): TypeMetadata;
}

export const isStatusIndicatorFactory = <T>(value: T): value is T & SearchStatusIndicatorFactory => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'createIndicator');
};

export const isSearchComponent = <T>(value: T): value is T & SearchComponentContract => {
    if (!isObject(value)) {
        return false;
    }
    if (!('isInitialized' in value) || typeof value['isInitialized'] !== 'boolean') {
        return false;
    }
    if (!hasFunctionProperty(value, 'initialize')) {
        return false;
    }
    if (!hasFunctionProperty(value, 'search')) {
        return false;
    }
    if (!hasFunctionProperty(value, 'searchFiles')) {
        return false;
    }
    if (!hasFunctionProperty(value, 'openPromptPreview')) {
        return false;
    }
    if (!hasFunctionProperty(value, 'getTypeMetadata')) {
        return false;
    }
    return true;
};

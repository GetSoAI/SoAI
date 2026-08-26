/* SoAI - Shared search types [frontend/assets/ts/core/search/searchTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

export interface SearchItem {
    id: string;
    name: string;
    description: string | null;
    type: string;
    category: string;
    score?: number | undefined;
    alias?: string | undefined;
    plugin?: string | undefined;
    component?: string | undefined;
    gpuIndex?: number | undefined;
    identifier?: string | null | undefined;
    metric?: string | undefined;
    badge?: string | undefined;
    icon?: IconName | undefined;
    iconTone?: 'messaging' | undefined;
    accessibleContext?: string | undefined;
    status?: string | undefined;
    filePath?: string | undefined;
    fileEntryType?: 'file' | 'directory' | undefined;
    configPath?: string | undefined;
}

export interface CachedSearch {
    results: SearchItem[];
    timestamp: number;
    partial: boolean;
}

export interface TypeMetadata {
    icon: IconName;
}

export interface SearchOptions {
    limit?: number | undefined;
    immediate?: boolean | undefined;
    presentation?: 'compact' | 'page' | undefined;
    signal?: AbortSignal | null | undefined;
}

export interface DeviceResultParameters {
    id: string;
    name: string;
    description: string | null;
    component: string;
    identifier?: string | null | undefined;
    metric: string;
    badge?: string | undefined;
    icon?: IconName | undefined;
    extra?: { gpuIndex?: number | undefined } | undefined;
}

export interface NavigationDetail {
    component?: string | undefined;
    resolvedRoute?: { component?: string | undefined } | undefined;
    route?: string | undefined;
}

export interface SearchIndex {
    models: Map<string, SearchItem>;
    plugins: Map<string, SearchItem>;
    devices: Map<string, SearchItem>;
    configs: Map<string, SearchItem>;
    pages: Map<string, SearchItem>;
    help: Map<string, SearchItem>;
    modals: Map<string, SearchItem>;
    powerActions: Map<string, SearchItem>;
}

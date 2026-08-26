/* SoAI - File explorer deep link construction [frontend/assets/ts/core/fileexplorerbrowser/deepLinks.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';

interface FileExplorerDeepLinkOptions {
    directoryPath: string;
    highlightPath: string | null;
    search: string | null;
    previewPath?: string | null | undefined;
}

const buildFileExplorerDeepLinkQuery = (options: FileExplorerDeepLinkOptions): Record<string, string> => {
    const query: Record<string, string> = {
        path: toVirtualPath(options.directoryPath)
    };
    if (options.highlightPath) {
        query['highlight'] = toVirtualPath(options.highlightPath);
    }
    const search = toTrimmedString(options.search ?? '');
    if (search) {
        query['search'] = search;
    }
    if (options.previewPath) {
        query['preview'] = toVirtualPath(options.previewPath);
    }
    return query;
};

const buildFileExplorerDeepLink = (options: FileExplorerDeepLinkOptions): string => {
    const query = buildFileExplorerDeepLinkQuery(options);
    const searchParameters = new URLSearchParams(query).toString();
    return searchParameters ? `#fileExplorer?${searchParameters}` : '#fileExplorer';
};

const resolveFileExplorerDeepLinkPath = (href: string | null): string | null => {
    const trimmed = toTrimmedString(href ?? '');
    if (!trimmed.startsWith('#fileExplorer?')) {
        return null;
    }
    const queryIndex = trimmed.indexOf('?');
    if (queryIndex < 0) {
        return null;
    }
    const path = new URLSearchParams(trimmed.slice(queryIndex + 1)).get('path');
    return path && path.trim() ? toVirtualPath(path) : null;
};

const buildFileExplorerSearchLink = (query: string): string => {
    const search = toTrimmedString(query);
    const searchParameters = new URLSearchParams({ search }).toString();
    return `#fileExplorer?${searchParameters}`;
};

export { buildFileExplorerDeepLink, buildFileExplorerDeepLinkQuery, buildFileExplorerSearchLink, resolveFileExplorerDeepLinkPath };
export type { FileExplorerDeepLinkOptions };

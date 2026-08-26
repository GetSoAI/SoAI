/* SoAI - Shared routing resource DOM contracts [frontend/assets/ts/core/routing/pages/collections/resource/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isString } from '@core/typeGuards.ts';
import type { CollectionConfig, HostInterface, LayoutElements, ResolvedCollectionLayout } from '@core/routing/pages/collections/resource/types.ts';
import { resolveCollectionConfig } from '@core/routing/pages/collections/resource/state.ts';

const getCollectionConfigOrNull = (host: HostInterface): CollectionConfig | null => {
    const config = resolveCollectionConfig(host);
    return config === null ? null : config;
};

const resolveGridId = (pageId: string, host: HostInterface): string | null => {
    const config = getCollectionConfigOrNull(host);
    return config?.gridId ? config.gridId : pageId ? `${pageId}-grid` : null;
};

const resolveEmptyStateId = (pageId: string, host: HostInterface): string | null => {
    const config = getCollectionConfigOrNull(host);
    return config?.emptyStateId ? config.emptyStateId : pageId ? `${pageId}-empty` : null;
};

const requireHostDomResolver = (host: HostInterface): ((selector: string, container?: Element) => HTMLElement | null) => {
    if (typeof host.optionalHTMLElement !== 'function') {
        throw new Error('Collection host must expose optionalHTMLElement before resolving the collection layout');
    }
    return (selector: string, container?: Element) => {
        if (typeof host.optionalHTMLElement !== 'function') {
            throw new Error('Collection host optionalHTMLElement resolver disappeared during layout resolution');
        }
        return host.optionalHTMLElement(selector, container);
    };
};

const getGridElement = (pageId: string, host: HostInterface): HTMLElement | null => {
    const gridId = resolveGridId(pageId, host);
    if (!gridId) {
        return null;
    }
    return requireHostDomResolver(host)(gridId);
};

const getEmptyStateElement = (pageId: string, host: HostInterface): HTMLElement | null => {
    const emptyStateId = resolveEmptyStateId(pageId, host);
    if (!emptyStateId) {
        return null;
    }
    return requireHostDomResolver(host)(emptyStateId);
};

const resolveLoadingElement = (pageId: string, host: HostInterface): HTMLElement => {
    const grid = getGridElement(pageId, host);
    if (grid) {
        return grid;
    }
    const empty = getEmptyStateElement(pageId, host);
    if (empty) {
        return empty;
    }
    throw new Error(`${pageId} loading target unavailable`);
};

const getLoadingTargetElement = (pageId: string, host: HostInterface): HTMLElement => {
    const element = resolveLoadingElement(pageId, host);
    if (!element) {
        const targetName = resolveGridId(pageId, host) || resolveEmptyStateId(pageId, host) || 'collection loading surface';
        throw new Error(`${pageId} loading target (${targetName}) could not be found`);
    }
    return element;
};

const ensureGridElement = (pageId: string, host: HostInterface): HTMLElement => {
    const grid = getGridElement(pageId, host);
    if (!grid) {
        const gridId = resolveGridId(pageId, host) || 'collection grid';
        throw new Error(`${pageId} requires ${gridId} to be present before continuing`);
    }
    return grid;
};

const resolveLayoutElements = (pageId: string, host: HostInterface): LayoutElements => ({
    grid: ensureGridElement(pageId, host),
    emptyState: getEmptyStateElement(pageId, host)
});

const getFilterBindings = (layout: ResolvedCollectionLayout): Record<string, string> | null => {
    const filters = layout.filters;
    if (!isObject(filters)) {
        return null;
    }
    const result: Record<string, string> = {};
    for (const [key, value] of Object.entries(filters)) {
        if (!isString(value) || !value.trim()) {
            throw new TypeError(`collection.layout.filters[${key}] must be a non-empty string`);
        }
        result[key] = value;
    }
    return result;
};

export { getEmptyStateElement, getFilterBindings, getGridElement, getLoadingTargetElement, resolveGridId, resolveLoadingElement, resolveEmptyStateId, resolveLayoutElements, ensureGridElement };

/* SoAI - Shared routing resource state [frontend/assets/ts/core/routing/pages/collections/resource/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { normalizeCollectionHeader } from '@core/routing/pages/collections/collectionHeaderNormalization.ts';
import { isArray, isFiniteNumber, isFunction, isNullOrUndefined, isObject, isPlainObject, isString } from '@core/typeGuards.ts';
import { FRAME_BUDGET_MS } from '@core/routing/pages/collections/resource/constants.ts';
import type { CollectionConfig, CollectionLayoutState, HostInterface, RawCollectionLayout, ResolvedCollectionLayout, WaitBudget, WaitOptions } from '@core/routing/pages/collections/resource/types.ts';
import { createLayoutAbortError, parseActionHandlerConfigList, parseDelegatedHandlerConfigList } from '@core/routing/pages/collections/resource/mappers.ts';

const createCollectionLayoutState = (): CollectionLayoutState => ({ value: null });

const captureHostLayoutFactory = (host: HostInterface, pageId: string): (() => RawCollectionLayout) | null => {
    if (!isObject(host)) {
        return null;
    }
    const layoutFunctionValueValue = host.defineCollectionLayout;
    if (!isFunction(layoutFunctionValueValue)) {
        return null;
    }
    return (): RawCollectionLayout => {
        if (!isFunction(host.defineCollectionLayout)) {
            throw new TypeError(`${pageId}.layout.defineCollectionLayout must be a function`);
        }
        const layout = host.defineCollectionLayout();
        if (layout === null || typeof layout !== 'object') {
            throw new TypeError(`${pageId}.layout.defineCollectionLayout must return an object`);
        }
        const actions = layout['actions'];
        const delegated = layout['delegated'];
        if (actions !== undefined && !isArray(actions)) throw new TypeError(`${pageId}.layout.actions must be an array`);
        if (delegated !== undefined && !isArray(delegated)) throw new TypeError(`${pageId}.layout.delegated must be an array`);

        const contentValue = layout['content'];
        if (!isNullOrUndefined(contentValue) && !isString(contentValue)) {
            throw new TypeError(`${pageId}.layout.content must be a string when provided`);
        }
        const resolvedLayout: RawCollectionLayout = {};
        if (layout.header !== undefined) {
            resolvedLayout.header = layout.header;
        }
        if (isString(contentValue)) {
            resolvedLayout.content = contentValue;
        }
        resolvedLayout.actions = actions ?? [];
        resolvedLayout.delegated = delegated ?? [];
        if (layout.filters !== undefined) {
            resolvedLayout.filters = layout.filters;
        }
        return resolvedLayout;
    };
};

const resolveCollectionConfig = (host: HostInterface): CollectionConfig | null => {
    if (!host.collections) {
        return null;
    }
    return host.collections.configuration();
};

const resolveCollectionLayout = (pageId: string, layoutState: CollectionLayoutState, defineCollectionLayout: () => RawCollectionLayout, hostLayoutFactory: (() => RawCollectionLayout) | null): ResolvedCollectionLayout => {
    if (!layoutState.value) {
        const sourceLayout = isFunction(hostLayoutFactory) ? hostLayoutFactory() : defineCollectionLayout();
        if (sourceLayout === null || typeof sourceLayout !== 'object') {
            throw new TypeError('Collection layout must be an object');
        }

        const { config: normalizedHeader, metadata: headerMetadata } = normalizeCollectionHeader(sourceLayout.header ?? null);
        const sourceActions = sourceLayout.actions ?? [];
        const sourceDelegated = sourceLayout.delegated ?? [];
        if (!isArray(sourceActions)) {
            throw new TypeError('Collection layout actions must be an array');
        }
        if (!isArray(sourceDelegated)) {
            throw new TypeError('Collection layout delegated must be an array');
        }

        const actions = parseActionHandlerConfigList(sourceActions, `${pageId}.layout.actions`);
        const delegated = parseDelegatedHandlerConfigList(sourceDelegated, `${pageId}.layout.delegated`);
        const filtersValue = sourceLayout.filters;
        let filters: Record<string, string> | null = null;
        if (filtersValue !== undefined && filtersValue !== null) {
            if (!isPlainObject(filtersValue)) {
                throw new TypeError(`${pageId}.layout.filters must be an object when provided`);
            }
            filters = {};
            for (const [key, value] of Object.entries(filtersValue)) {
                if (!isString(value) || !value.trim()) {
                    throw new TypeError(`${pageId}.layout.filters[${key}] must be a non-empty string`);
                }
                filters[key] = value;
            }
        }

        layoutState.value = {
            header: normalizedHeader,
            headerMetadata: headerMetadata || null,
            content: sourceLayout.content ?? '',
            filters,
            actions,
            delegated
        };
    }

    const layout = layoutState.value;
    if (!layout) {
        throw new Error(`${pageId} collection layout is unavailable`);
    }
    return {
        header: layout.header,
        headerMetadata: layout.headerMetadata ?? null,
        content: layout.content,
        filters: layout.filters,
        actions: layout.actions,
        delegated: layout.delegated
    };
};

const resolveWaitSignal = (host: HostInterface, options: WaitOptions = {}): AbortSignal | null => {
    if (options.signal) {
        return options.signal;
    }
    if (isFunction(host.getRuntimeAbortSignal)) {
        return host.getRuntimeAbortSignal();
    }
    return null;
};

const resolveWaitTimeout = (timeoutCandidate: number | undefined, defaultTimeout: number, attemptsCandidate: number | undefined): number => {
    if (isFiniteNumber(timeoutCandidate)) {
        return Math.max(0, timeoutCandidate);
    }
    if (isFiniteNumber(attemptsCandidate)) {
        return Math.max(0, attemptsCandidate) * FRAME_BUDGET_MS;
    }
    return defaultTimeout;
};

const resolveWaitBudget = (host: HostInterface, options: WaitOptions = {}, defaultTimeout = 0): WaitBudget => ({
    timeoutMs: resolveWaitTimeout(options.timeoutMs, defaultTimeout, options.attempts),
    signal: resolveWaitSignal(host, options)
});

const assertActiveLayout = (pageId: string, host: HostInterface, signal: AbortSignal | null, identifier: string | null): void => {
    if (signal?.aborted) {
        throw createLayoutAbortError(pageId, identifier, 'aborted');
    }
    if (host?.isDestroyed) {
        throw createLayoutAbortError(pageId, identifier, 'destroyed');
    }
};

const awaitLayoutFrame = async (pageId: string, host: HostInterface, signal: AbortSignal | null): Promise<void> => {
    const requestAnimationFrame = getRequestAnimationFrame();
    await new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
            resolve();
        });
    });
    assertActiveLayout(pageId, host, signal, 'animation frame');
};

const waitForLayoutElement = async (pageId: string, host: HostInterface, resolver: () => HTMLElement | null, identifier: string | null, options: WaitBudget): Promise<HTMLElement> => {
    if (!isFunction(resolver)) {
        throw new TypeError('CollectionResource requires a resolver function when waiting for layout elements');
    }
    const signal = options.signal;
    const timeoutMs = isFiniteNumber(options.timeoutMs) ? Math.max(0, options.timeoutMs) : 0;
    const deadline = timeoutMs === 0 ? performance.now() : performance.now() + timeoutMs;
    assertActiveLayout(pageId, host, signal, identifier);

    let target = resolver();
    while (!target && performance.now() <= deadline) {
        await awaitLayoutFrame(pageId, host, signal);
        target = resolver();
    }

    if (!target) {
        const label = identifier || 'target element';
        if (signal?.aborted) {
            throw createLayoutAbortError(pageId, label, 'aborted');
        }
        const reason = timeoutMs === 0 ? 'unavailable' : 'timeout';
        throw new Error(`${pageId} requires ${label} before continuing (${reason})`);
    }
    return target;
};

export { assertActiveLayout, captureHostLayoutFactory, createCollectionLayoutState, resolveCollectionConfig, resolveCollectionLayout, resolveWaitBudget, waitForLayoutElement };

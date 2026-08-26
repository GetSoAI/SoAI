/* SoAI - Shared component support collection [frontend/assets/ts/core/componentsupport/collection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionsStore } from '@core/CollectionsStore.ts';
import { logError } from '@core/componentsupport/logger.ts';
import type { CollectionConfigOptions, PageInstance, RealtimeConfig } from '@core/componentsupport/types.ts';
import type { RealtimeCollectionRuntimeConfig } from '@core/realtime/collectionContracts.ts';
import { create } from '@core/realtimeCollections.ts';
import type { RealtimeLifecycleArgument } from '@core/componentsupport/realtimeLifecycle.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const configureCollection = (page: PageInstance, options: CollectionConfigOptions = {}): { collection: PageInstance['collection'] } => {
    if (!page) {
        throw new TypeError('collectionSupport.configure requires a page instance');
    }

    const collectionOptions = options.collectionOptions ?? {};
    page.collection = page.collection ?? new CollectionsStore(collectionOptions);

    if (options.realtime) {
        if (!isObject(options.realtime)) {
            throw new TypeError('collectionSupport.configure realtime config must be an object');
        }
        const input: RealtimeConfig = options.realtime;
        const subscribe = input.subscribe;
        if (!isFunction(subscribe)) {
            throw new TypeError('collectionSupport.configure realtime config requires subscribe');
        }
        const extraHandlers = input.handlers;
        if (extraHandlers !== undefined && !isObject(extraHandlers)) {
            throw new TypeError('collectionSupport.configure realtime handlers must be an object');
        }

        const baseHandlers: Record<string, ((...inputArguments: RealtimeLifecycleArgument[]) => void) | undefined> = {
            onInitial: (...inputArguments: RealtimeLifecycleArgument[]) => {
                const onData = options.realtime?.['onData'];
                if (isFunction(onData)) onData(...inputArguments);
            },
            onUpdate: options.realtime['onData'],
            onError: (error: RealtimeLifecycleArgument) => logError('CollectionPage', 'Connection error', error)
        };

        const resolveHandler = (name: string): ((...inputArguments: RealtimeLifecycleArgument[]) => void) | undefined => {
            const base = baseHandlers[name];
            const extra = extraHandlers ? extraHandlers[name] : undefined;
            const baseFunctionValue = isFunction(base) ? base : null;
            const extraFunctionValue = isFunction(extra) ? extra : null;
            if (baseFunctionValue && extraFunctionValue) {
                return (...inputArguments: RealtimeLifecycleArgument[]): void => {
                    void baseFunctionValue(...inputArguments);
                    void extraFunctionValue(...inputArguments);
                };
            }
            if (extraFunctionValue) {
                return (...inputArguments: RealtimeLifecycleArgument[]): void => void extraFunctionValue(...inputArguments);
            }
            if (baseFunctionValue) {
                return (...inputArguments: RealtimeLifecycleArgument[]): void => void baseFunctionValue(...inputArguments);
            }
            return undefined;
        };

        const config: RealtimeCollectionRuntimeConfig = { subscribe };
        if (input.key !== undefined) config.key = input.key;
        if (input.endpoint !== undefined) config.endpoint = input.endpoint;
        if (input.resource !== undefined) config.resource = input.resource;
        const fetchFunctionValue = input.fetch;
        if (fetchFunctionValue !== undefined) config.fetch = () => fetchFunctionValue(page);
        if (input.decorate !== undefined) config.decorate = input.decorate;
        if (input.immediate !== undefined) config.immediate = input.immediate;
        if (input.autoStart !== undefined) config.autoStart = input.autoStart;
        if (input.onWarningStateChange !== undefined) config.onWarningStateChange = input.onWarningStateChange;

        const onInitial = resolveHandler('onInitial');
        if (onInitial) config.onInitial = onInitial;
        const onUpdate = resolveHandler('onUpdate');
        if (onUpdate) config.onUpdate = onUpdate;
        const onConnect = resolveHandler('onConnect');
        if (onConnect) config.onConnect = onConnect;
        const onError = resolveHandler('onError');
        if (onError) config.onError = onError;
        const onFirstError = resolveHandler('onFirstError');
        if (onFirstError) config.onFirstError = onFirstError;
        const onReconnecting = resolveHandler('onReconnecting');
        if (onReconnecting) config.onReconnecting = onReconnecting;
        const onReconnectFailed = resolveHandler('onReconnectFailed');
        if (onReconnectFailed) config.onReconnectFailed = onReconnectFailed;
        const onStartError = resolveHandler('onStartError');
        if (onStartError) config.onStartError = onStartError;
        const onFetchError = resolveHandler('onFetchError');
        if (onFetchError) config.onFetchError = onFetchError;
        const onFetchSuccess = resolveHandler('onFetchSuccess');
        if (onFetchSuccess) config.onFetchSuccess = onFetchSuccess;
        const onManagerUnavailable = resolveHandler('onManagerUnavailable');
        if (onManagerUnavailable) config.onManagerUnavailable = onManagerUnavailable;

        void create(page, config);
    }

    return { collection: page.collection };
};

export { configureCollection };

/* SoAI - Shared routing resource actions [frontend/assets/ts/core/routing/pages/collections/resource/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RunPageTaskOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { WaitOptions, WithLoadingOptions } from '@core/routing/pages/collections/resource/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
interface CollectionLoadingContext {
    pageId: string;
    waitForLoadingElement: (options: WaitOptions) => Promise<HTMLElement>;
    runPageTask: <T>(taskName: string, task: () => Promise<T>, options: RunPageTaskOptions<T>) => Promise<T | null>;
}

const executeWithRunTask = async <T extends JsonValue | null>(context: CollectionLoadingContext, task: () => Promise<T>, options: WithLoadingOptions<T>): Promise<T | null> => {
    const waitSignal = options.signal;
    const loadingElement = await context.waitForLoadingElement({ signal: waitSignal ?? undefined });
    const runOptions: RunPageTaskOptions<T> = {
        loadingElement,
        displayName: options.displayName || options.errorPrefix || context.pageId || 'Collection task'
    };
    if (options.rethrow !== undefined) {
        runOptions.rethrow = options.rethrow;
    }
    if (options.loadingText !== undefined) {
        runOptions.loadingText = options.loadingText;
    }
    if (options.successMessage !== undefined) {
        runOptions.successMessage = options.successMessage;
    }
    if (typeof options.onSuccess === 'function') {
        runOptions.onSuccess = options.onSuccess;
    }
    if (typeof options.onError === 'function') {
        runOptions.onError = options.onError;
    }
    if (typeof options.onFinally === 'function') {
        runOptions.onFinally = options.onFinally;
    }
    return context.runPageTask(options.taskName || `${context.pageId || 'collection'}.withLoading`, task, runOptions);
};

const withLoading = async <T extends JsonValue | null>(context: CollectionLoadingContext, task: () => Promise<T>, options: WithLoadingOptions<T> = {}): Promise<T | null> => {
    if (typeof task !== 'function') {
        throw new TypeError('CollectionResource.withLoading requires a function');
    }

    return executeWithRunTask(context, task, options);
};

export { withLoading };

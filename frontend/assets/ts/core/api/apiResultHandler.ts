/* SoAI - Shared API result handler [frontend/assets/ts/core/api/apiResultHandler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, type APIErrorMetadataValue } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { requireApiNotificationBridge } from '@core/api/notificationBridge.ts';
import { resolveApiErrorMessage } from '@core/api/errorPayloads.ts';
import { normalizeRuntimeErrorValue } from '@core/api/mappers.ts';
import { isFunction, isString } from '@core/typeGuards.ts';

type RethrowDecider = boolean | ((error: APIErrorMetadataValue) => boolean);

interface ApiResultHandlerOptions {
    notifySuccessMessage?: string;
    notifyErrorMessage?: string;
    notifyOnSuccess?: boolean;
    notifyOnError?: boolean;
    notifyNetworkErrors?: boolean;
    logErrors?: boolean;
    silent?: boolean;
    boundaryName?: string;
    onError?: (error: APIErrorMetadataValue) => void;
    rethrow?: RethrowDecider;
}

const resolveErrorMessage = (error: APIErrorMetadataValue, options: ApiResultHandlerOptions): string => {
    if (isString(options.notifyErrorMessage) && options.notifyErrorMessage) return options.notifyErrorMessage;
    return resolveApiErrorMessage(error) ?? '';
};

const resolveSuccessMessage = (options: ApiResultHandlerOptions): string => {
    if (isString(options.notifySuccessMessage) && options.notifySuccessMessage) return options.notifySuccessMessage;
    return '';
};

const shouldRethrow = (error: APIErrorMetadataValue, rethrow: RethrowDecider | undefined): boolean => {
    if (typeof rethrow === 'function') return rethrow(error);
    return rethrow !== false;
};

const handleApiResult = async <T>(promise: Promise<T>, options: ApiResultHandlerOptions = {}): Promise<T | null> => {
    const notifyOnError = options.notifyOnError !== false;
    const notifyOnSuccess = options.notifyOnSuccess === true;
    const notifyNetworkErrors = options.notifyNetworkErrors !== false;
    const logErrors = options.logErrors !== false;
    const silent = options.silent === true;
    const boundaryName = isString(options.boundaryName) && options.boundaryName ? options.boundaryName : 'Api';

    const notificationBridge = !silent && (notifyOnSuccess || notifyOnError) ? requireApiNotificationBridge() : null;

    try {
        const result = await promise;
        if (!silent && notifyOnSuccess) {
            const message = resolveSuccessMessage(options);
            if (message && notificationBridge) notificationBridge.showNotification(message, 'success', 3000);
        }
        return result;
    } catch (error) {
        const runtimeError = normalizeRuntimeErrorValue(error);
        if (isFunction(options.onError)) {
            try {
                options.onError(runtimeError);
            } catch (handlerError) {
                const runtimeHandlerError = normalizeRuntimeErrorValue(handlerError);
                errorHandler.warn(boundaryName, 'Api result onError handler failed', runtimeHandlerError);
            }
        }

        const networkError = isNetworkError(runtimeError);
        if (!silent && logErrors) {
            errorHandler.error(boundaryName, 'Api call failed', runtimeError);
        }

        if (!silent && notifyOnError && (!networkError || notifyNetworkErrors)) {
            const message = resolveErrorMessage(runtimeError, options);
            const handledByNotifier = notificationBridge ? notificationBridge.notifyHandledOperationError(runtimeError) : false;
            if (!handledByNotifier && message && notificationBridge) notificationBridge.showNotification(message, 'error', 6000);
        }

        if (shouldRethrow(runtimeError, options.rethrow)) {
            throw runtimeError;
        }
        return null;
    }
};

export { handleApiResult };
export type { ApiResultHandlerOptions, RethrowDecider };

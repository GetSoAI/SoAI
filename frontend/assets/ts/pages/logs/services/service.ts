/* SoAI - Logs page services service [frontend/assets/ts/pages/logs/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { closeDetachedRuntimeWindowsByPage, openDetachedRuntimeWindow } from '@core/runtimeenv/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { VALID_LOG_LINE_LIMITS } from '@core/logvalidation/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { LogStreamService, StreamPayload } from '@pages/logs/types.ts';

const resolveLogLineOptionsFromStorage = (_storage: StorageService | null | undefined): readonly number[] => VALID_LOG_LINE_LIMITS;

const isLogStreamService = (value: LogStreamService | JsonValue | null | undefined): value is LogStreamService => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'subscribe');
};

const requireLogStreamService = (value: LogStreamService | JsonValue | null | undefined): LogStreamService => {
    if (!isLogStreamService(value)) {
        throw new Error('LogStreamService is not available');
    }
    return value;
};

interface SubscribeLogsStreamArguments {
    moduleValue: LogStreamService | JsonValue | null | undefined;
    logLineLimit: number;
    logSource: string;
    previousUnsubscribe: (() => void) | null;
    onPayload: (payload: StreamPayload) => void;
}

const subscribeLogsStream = (inputArguments: SubscribeLogsStreamArguments): (() => void) => {
    const service = requireLogStreamService(inputArguments.moduleValue);
    if (inputArguments.previousUnsubscribe) {
        inputArguments.previousUnsubscribe();
    }
    return service.subscribe(inputArguments.onPayload, { replayLimit: inputArguments.logLineLimit, source: inputArguments.logSource });
};

const openLogsDetachedWindow = (): void => {
    closeDetachedRuntimeWindowsByPage('logs');
    openDetachedRuntimeWindow('logs', {
        title: i18n.t('logs.windowTitle')
    });
};

export { isLogStreamService, openLogsDetachedWindow, resolveLogLineOptionsFromStorage, subscribeLogsStream };

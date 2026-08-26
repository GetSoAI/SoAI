/* SoAI - Shared operation progress payloads [frontend/assets/ts/core/operationprogress/payloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isNullOrUndefined, isNumber, isThenable, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { OperationProgressData, OperationProgressOptions } from '@core/operationprogress/types.ts';

type OperationProgressCancelHandler = NonNullable<OperationProgressOptions['onCancel']>;
type OperationProgressState = NonNullable<OperationProgressData['state']>;

interface OperationProgressUpdatePayload {
    messageValue: string | undefined;
    badgeValue: string | undefined;
    detailsValue: string | undefined;
    progressValue: number | undefined;
    stateValue: OperationProgressState | undefined;
    cancelableValue: boolean | undefined;
}

const DEFAULT_OPERATION_PROGRESS_CANCEL_SELECTOR = 'button[data-operation-progress-action="cancel"]';

const isOperationProgressCancelHandler = (value: OperationProgressOptions['onCancel'] | null | undefined): value is OperationProgressCancelHandler => isFunction(value);

const readBooleanOption = (value: boolean | null | undefined, defaultValue: boolean): boolean => {
    if (isNullOrUndefined(value)) {
        return defaultValue;
    }
    if (typeof value === 'boolean') {
        return value;
    }
    throw new TypeError('Operation progress option must be a boolean when provided');
};

const readStringOption = (value: string | null | undefined, defaultValue: string | null): string | null => {
    if (isNullOrUndefined(value)) {
        return defaultValue;
    }
    if (!isString(value)) {
        throw new TypeError('Operation progress option must be a string when provided');
    }
    const normalized = value.trim();
    return normalized ? normalized : null;
};

const readOnCancelOption = (value: OperationProgressOptions['onCancel'] | null | undefined): OperationProgressCancelHandler | null => {
    if (isNullOrUndefined(value)) {
        return null;
    }
    if (!isOperationProgressCancelHandler(value)) {
        throw new TypeError('Operation progress onCancel must be a function when provided');
    }
    const onCancelHandler = value;
    return (key, context) => {
        const result = onCancelHandler(key, context);
        if (isNullOrUndefined(result)) {
            return;
        }
        if (isThenable(result)) {
            return Promise.resolve(result).then((): void => {});
        }
        throw new TypeError('Operation progress onCancel must return void or Promise<void>');
    };
};

const readOptionalStringField = (value: JsonValue | null | undefined, fieldName: string): string | undefined => {
    if (isNullOrUndefined(value)) {
        return undefined;
    }
    if (!isString(value)) {
        throw new TypeError(`Operation progress ${fieldName} must be a string when provided`);
    }
    return value;
};

const readOptionalProgress = (value: JsonValue | null | undefined): number | undefined => {
    if (isNullOrUndefined(value)) {
        return undefined;
    }
    if (!isNumber(value)) {
        throw new TypeError('Operation progress progress must be a number when provided');
    }
    return value;
};

const readOptionalState = (value: JsonValue | null | undefined): OperationProgressState | undefined => {
    if (isNullOrUndefined(value)) {
        return undefined;
    }
    if (!isString(value)) {
        throw new TypeError('Operation progress state must be a string when provided');
    }
    switch (value) {
        case 'success':
        case 'error':
        case 'downloading':
        case 'pending':
        case 'info':
            return value;
        default:
            throw new TypeError('Operation progress state is invalid');
    }
};

const readOptionalBooleanField = (value: JsonValue | null | undefined, fieldName: string): boolean | undefined => {
    if (isNullOrUndefined(value)) {
        return undefined;
    }
    if (typeof value !== 'boolean') {
        throw new TypeError(`Operation progress ${fieldName} must be a boolean when provided`);
    }
    return value;
};

const normalizeOperationProgressOptions = (options: OperationProgressOptions | null | undefined): OperationProgressOptions => {
    if (isNullOrUndefined(options)) {
        return { showCancel: true, showBadge: true, cancelSelector: DEFAULT_OPERATION_PROGRESS_CANCEL_SELECTOR, onCancel: null, backgroundButtonId: null, extraClassName: null };
    }
    if (typeof options !== 'object' || Array.isArray(options)) {
        throw new TypeError('Operation progress options must be an object when provided');
    }
    const requestedShowCancel = readBooleanOption(options['showCancel'], true);
    const showBadge = readBooleanOption(options['showBadge'], true);
    const cancelSelector = readStringOption(options['cancelSelector'], DEFAULT_OPERATION_PROGRESS_CANCEL_SELECTOR);
    const backgroundButtonId = readStringOption(options['backgroundButtonId'], null);
    const extraClassName = readStringOption(options['extraClassName'], null);
    const onCancel = readOnCancelOption(options['onCancel']);
    return {
        showCancel: requestedShowCancel && onCancel !== null,
        showBadge,
        cancelSelector,
        backgroundButtonId,
        extraClassName,
        onCancel
    };
};

const readOperationProgressUpdatePayload = (data: OperationProgressData): OperationProgressUpdatePayload => {
    if (data === null || typeof data !== 'object' || Array.isArray(data)) {
        throw new TypeError('Operation progress update data must be an object');
    }
    return {
        messageValue: readOptionalStringField(data['message'], 'message'),
        badgeValue: readOptionalStringField(data['badge'], 'badge'),
        detailsValue: readOptionalStringField(data['details'], 'details'),
        progressValue: readOptionalProgress(data['progress']),
        stateValue: readOptionalState(data['state']),
        cancelableValue: readOptionalBooleanField(data['cancelable'], 'cancelable')
    };
};

export { normalizeOperationProgressOptions, readOperationProgressUpdatePayload };
export type { OperationProgressUpdatePayload };

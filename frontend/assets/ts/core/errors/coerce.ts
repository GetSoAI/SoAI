/* SoAI - Shared errors coerce [frontend/assets/ts/core/errors/coerce.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isNumber, isString } from '@core/typeGuards.ts';

type ErrorFieldPrimitive = string | number | boolean | bigint | symbol | null | undefined | void;

type ErrorFieldFunction = (...inputArguments: never[]) => ErrorFieldValue;

interface ErrorFieldRecord {
    readonly [key: string]: ErrorFieldValue;
}

type ErrorFieldArray = readonly ErrorFieldValue[];

type ErrorFieldValue = ErrorFieldPrimitive | Error | ErrorFieldArray | ErrorFieldFunction | ErrorFieldRecord;

interface ErrorMessageFieldExtractionOptions {
    includeValueString?: boolean;
    includeStringifiedFallback?: boolean;
    preferFields?: boolean;
    includeErrorMessage?: boolean;
}

const API_ERROR_MESSAGE_FIELDS: readonly string[] = ['response.data', 'response.data.detail', 'response.data.message', 'response.data.error_message', 'response.data.error.detail', 'response.data.error.message', 'response.data.error.reason', 'response.data.error', 'response.data.reason', 'data', 'data.detail', 'data.message', 'data.error_message', 'data.error.detail', 'data.error.message', 'data.error.reason', 'data.error', 'data.reason', 'detail.message', 'detail.error_message', 'detail.user_message', 'detail', 'reason', 'payload.error_message', 'payload.error.detail', 'payload.error.message', 'payload.error.reason', 'payload.error', 'payload.detail', 'payload.message', 'payload.reason', 'error_message', 'message', 'statusText'];
const USER_FACING_ERROR_MESSAGE_FIELDS: readonly string[] = ['user_message', 'error_message', 'message', 'detail.user_message', 'detail.error_message', 'detail.message', 'detail', 'error.user_message', 'error.error_message', 'error.message', 'error', 'description'];
const ERROR_CODE_FIELDS: readonly string[] = ['code', 'error_type', 'error.code', 'error.type', 'data.code', 'data.error_type', 'data.error.code', 'data.error.type', 'detail.code', 'detail.type', 'payload.code', 'payload.error_type', 'payload.error.code', 'payload.error.type', 'response.data.code', 'response.data.error_type', 'response.data.error.code', 'response.data.error.type', 'response.data.detail.code', 'response.data.detail.type'];

const ensureError = <T>(value: T): Error => {
    if (value instanceof Error) return value;
    return new Error(String(value));
};

const isErrorFieldRecord = <T>(value: T): value is T & ErrorFieldRecord => {
    if (value === null || value === undefined) {
        return false;
    }
    return typeof value === 'object' || typeof value === 'function';
};

const readErrorFieldValue = <T>(value: T, field: string): ErrorFieldValue => {
    if (!isErrorFieldRecord(value)) {
        return undefined;
    }
    return value[field];
};

const readErrorPathValue = <T>(value: T, path: readonly string[]): ErrorFieldValue => {
    let current: ErrorFieldValue = value instanceof Error ? value : readErrorFieldValue({ value }, 'value');
    for (const segment of path) {
        if (!isErrorFieldRecord(current)) {
            return null;
        }
        current = current[segment];
    }
    return current;
};

const coerceErrorMessage = <T>(value: T, fallback?: string): string => {
    if (value instanceof Error) {
        const message = toTrimmedString(value.message);
        if (message) {
            return message;
        }
        if (fallback !== undefined) {
            return fallback;
        }
    }
    if (isErrorFieldRecord(value)) {
        const message = toTrimmedString(value['message']);
        if (message) {
            return message;
        }
    }
    if (fallback !== undefined) {
        return fallback;
    }
    return String(value);
};

const extractErrorMessage = <T>(value: T): string | null => {
    if (value instanceof Error) {
        const message = toTrimmedString(value.message);
        if (message) {
            return message;
        }
    }
    if (isErrorFieldRecord(value)) {
        const message = toTrimmedString(value['message']);
        if (message) {
            return message;
        }
        const detail = toTrimmedString(value['detail']);
        if (detail) {
            return detail;
        }
        const error = toTrimmedString(value['error']);
        if (error) {
            return error;
        }
        const errorMessage = toTrimmedString(value['error_message']);
        if (errorMessage) {
            return errorMessage;
        }
    }
    const directMessage = toTrimmedString(value);
    if (directMessage) {
        return directMessage;
    }
    return null;
};

const normalizeMessageCandidate = <T>(value: T): string | null => {
    const message = toTrimmedString(value);
    return message || null;
};

const normalizeStringifiedMessageCandidate = <T>(value: T): string | null => {
    if (value === null || value === undefined) return null;
    const message = String(value).trim();
    if (!message || message === '[object Object]') return null;
    return message;
};

const extractErrorMessageByFields = <T>(value: T, fields: readonly string[], options: ErrorMessageFieldExtractionOptions = {}): string | null => {
    const includeErrorMessage = options.includeErrorMessage !== false;
    if (options.includeValueString) {
        const message = normalizeMessageCandidate(value);
        if (message) return message;
    }
    if (!options.preferFields && includeErrorMessage && value instanceof Error) {
        const message = normalizeMessageCandidate(value.message);
        if (message) return message;
    }
    for (const field of fields) {
        const message = normalizeMessageCandidate(readErrorPathValue(value, field.split('.')));
        if (message) return message;
    }
    if (options.preferFields && includeErrorMessage && value instanceof Error) {
        const message = normalizeMessageCandidate(value.message);
        if (message) return message;
    }
    if (options.includeStringifiedFallback) {
        return normalizeStringifiedMessageCandidate(value);
    }
    return null;
};

const readHttpStatus = <T>(value: T): number | null => {
    if (!isErrorFieldRecord(value)) {
        return null;
    }
    const status = value['status'];
    if (isNumber(status) && Number.isFinite(status)) {
        return status;
    }
    const response = value['response'];
    if (!isErrorFieldRecord(response)) {
        return null;
    }
    const responseStatus = response['status'];
    return isNumber(responseStatus) && Number.isFinite(responseStatus) ? responseStatus : null;
};

const isErrorHttpStatus = <T>(value: T, statusCode: number): boolean => readHttpStatus(value) === statusCode;

const extractErrorCode = <T>(value: T): string | null => {
    for (const field of ERROR_CODE_FIELDS) {
        const code = toTrimmedString(readErrorPathValue(value, field.split('.')));
        if (code) {
            return code;
        }
    }
    return null;
};

const extractApiErrorMessage = <T>(value: T): string | null => {
    const fieldMessage = extractErrorMessageByFields(value, API_ERROR_MESSAGE_FIELDS, {
        includeValueString: true,
        preferFields: true,
        includeErrorMessage: false
    });
    if (fieldMessage) {
        return fieldMessage;
    }
    return extractErrorMessageByFields(value, [], {
        includeStringifiedFallback: true
    });
};

const extractUserFacingErrorMessage = <T>(value: T): string | null => {
    return extractErrorMessageByFields(value, USER_FACING_ERROR_MESSAGE_FIELDS, {
        includeValueString: true,
        includeStringifiedFallback: true
    });
};

const requireErrorMessage = <T>(value: T, fallback: string): string => extractErrorMessage(value) ?? fallback;

const normalizeErrorTelemetryFields = <T>(error: T): Record<string, string> | null => {
    if (!error) return null;
    const output: Record<string, string> = {};
    if (isErrorFieldRecord(error)) {
        const name = error['name'];
        const message = error['message'];
        const stack = error['stack'];
        if (isString(name) && name) output['name'] = name;
        if (isString(message) && message) output['message'] = message;
        if (isString(stack) && stack) output['stack'] = stack;
    }
    if (!Object.keys(output).length) {
        output['message'] = String(error);
    }
    return output;
};

export { coerceErrorMessage, ensureError, extractApiErrorMessage, extractErrorCode, extractErrorMessage, extractErrorMessageByFields, extractUserFacingErrorMessage, isErrorHttpStatus, normalizeErrorTelemetryFields, requireErrorMessage };

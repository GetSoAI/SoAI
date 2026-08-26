/* SoAI - Shared frontend API error [frontend/assets/ts/core/apiError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';

interface APIErrorMetadataRecord {
    readonly [key: string]: APIErrorMetadataValue;
}

type APIErrorMetadataPrimitive = string | number | boolean | bigint | symbol | null | undefined | void;

type APIErrorMetadataValue = APIErrorMetadataPrimitive | ApiResponsePayload | Error | APIErrorMetadataRecord | readonly APIErrorMetadataValue[];

interface APIErrorMetadata {
    code?: string;
    detail?: APIErrorMetadataValue;
    reason?: string;
    cause?: APIErrorMetadataValue;
    data?: APIErrorMetadataValue;
    traceId?: string;
    payload?: APIErrorMetadataValue;
    endpoint?: string;
    taskId?: string;
    retryAfterSeconds?: number;
}

class APIError extends Error {
    readonly status: number;
    code?: string;
    detail?: APIErrorMetadataValue;
    reason?: string;
    declare cause?: APIErrorMetadataValue;
    data?: APIErrorMetadataValue;
    traceId?: string;
    payload?: APIErrorMetadataValue;
    endpoint?: string;
    taskId?: string;
    retryAfterSeconds?: number;

    constructor(status: number, message: string, metadata: APIErrorMetadata = {}) {
        super(message || 'Request failed');
        this.name = 'APIError';
        this.status = status;
        if (!metadata || typeof metadata !== 'object') return;

        if ('code' in metadata && metadata.code !== undefined) this.code = metadata.code;
        if ('detail' in metadata) this.detail = metadata.detail;
        if ('reason' in metadata && metadata.reason !== undefined) this.reason = metadata.reason;
        if ('cause' in metadata) this.cause = metadata.cause;
        if ('data' in metadata) this.data = metadata.data;
        if ('traceId' in metadata && metadata.traceId !== undefined) this.traceId = metadata.traceId;
        if ('payload' in metadata) this.payload = metadata.payload;
        if ('endpoint' in metadata && metadata.endpoint !== undefined) this.endpoint = metadata.endpoint;
        if ('taskId' in metadata && metadata.taskId !== undefined) this.taskId = metadata.taskId;
        if ('retryAfterSeconds' in metadata && metadata.retryAfterSeconds !== undefined) this.retryAfterSeconds = metadata.retryAfterSeconds;
    }
}

const isApiErrorFieldRecord = <T>(value: T): value is T & APIErrorMetadataRecord => {
    if (value === null || value === undefined) {
        return false;
    }
    return typeof value === 'object' || typeof value === 'function';
};

const readApiErrorField = <T>(value: T, key: string): APIErrorMetadataValue => {
    if (!isApiErrorFieldRecord(value)) {
        return undefined;
    }
    return value[key];
};

const isNetworkError = <T>(error: T): boolean => {
    if (error === null || error === undefined) return false;
    if (error instanceof APIError && error.status === 0) return true;
    if (!isApiErrorFieldRecord(error)) return false;

    const codeValue = readApiErrorField(error, 'code');
    const causeValue = readApiErrorField(error, 'cause');
    const causeCodeValue = isApiErrorFieldRecord(causeValue) ? readApiErrorField(causeValue, 'code') : null;
    const codeCandidate = typeof codeValue === 'string' ? codeValue : typeof causeCodeValue === 'string' ? causeCodeValue : '';
    if (codeCandidate && codeCandidate.toLowerCase().includes('network')) return true;

    const messageValue = readApiErrorField(error, 'message');
    const message = typeof messageValue === 'string' ? messageValue : '';
    return message.includes('NetworkError') || message.includes('Failed to fetch');
};

const isRequestTimeoutError = <T>(error: T): boolean => {
    if (!(error instanceof APIError)) {
        return false;
    }
    return error.status === 0 && error.message === 'Request timed out';
};

const isNonRetryableApiRequestError = <T>(error: T): boolean => error instanceof APIError && (error.status === 400 || error.status === 422);

export { APIError, isNetworkError, isNonRetryableApiRequestError, isRequestTimeoutError, readApiErrorField };

export type { APIErrorMetadata, APIErrorMetadataRecord, APIErrorMetadataValue };

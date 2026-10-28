/* SoAI - Shared frontend operation error notifier [frontend/assets/ts/core/operationErrorNotifier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, type APIErrorMetadataValue } from '@core/apiError.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import type { StreamTaskRuntime } from '@core/realtime/streammanager/actions/service.ts';
import type { TaskTerminalEvent, TaskTerminalListener } from '@core/realtime/streammanager/types.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveSkillErrorMessage } from '@core/skills/errorPresentation.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { readApiErrorDetail } from '@core/api/errorPayloads.ts';
import { readSpeechSetupReason } from '@core/speechsetup/failure.ts';
import { notifyObservedSpeechOutcome } from '@core/speechsetup/notifications.ts';
import { resolveObservedSpeechReason } from '@core/speechsetup/service.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';

interface NormalizedOperationError {
    taskId: string | null;
    code: string | null;
    status: number | null;
    message: string;
    errorCode: number | null;
    errorMessage: string | null;
    isOfflinePolicy: boolean;
    isInsufficientDiskSpace: boolean;
}

interface TaskFailureMetadata {
    taskId?: string | null;
    status?: string | null;
    code?: string | null;
    errorCode?: number | null;
    errorMessage?: string | null;
    errorType?: string | null;
    payload?: OperationErrorValue;
}

interface OperationErrorRecord {
    readonly [key: string]: OperationErrorValue;
}

type OperationErrorValue = APIErrorMetadataValue | APIError | TaskFailureError | OperationErrorRecord;

const HANDLED_TASK_TTL_MS = minutesToMs(10);
const HANDLED_ERROR_SIGNATURE_TTL_MS = 1500;
const handledTaskIds = new Map<string, number>();
const handledErrorSignatures = new Map<string, number>();

const pruneTimestampMap = (timestamps: Map<string, number>, ttlMs: number): void => {
    const now = Date.now();
    timestamps.forEach((timestamp, key) => {
        if (now - timestamp > ttlMs) {
            timestamps.delete(key);
        }
    });
};

const isOperationErrorRecord = <T>(value: T): value is T & OperationErrorRecord => value !== null && value !== undefined && typeof value === 'object';

const isOperationErrorValue = <T>(value: T): value is T & OperationErrorValue => typeof value !== 'function';

const normalizeTaskId = <T>(value: T): string | null => {
    const normalized = toTrimmedString(value);
    return normalized ? normalized : null;
};

const normalizeErrorCode = <T>(value: T): number | null => {
    if (typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value)) {
        return value;
    }
    if (typeof value === 'string' && value.trim()) {
        const parsed = Number.parseInt(value, 10);
        if (Number.isInteger(parsed)) {
            return parsed;
        }
    }
    return null;
};

const normalizeErrorMessage = <T>(value: T): string | null => {
    const normalized = toTrimmedString(value);
    return normalized ? normalized : null;
};

const readNestedTaskId = <T>(value: T): string | null => {
    if (!isOperationErrorRecord(value)) {
        return null;
    }
    const errorRecord = isOperationErrorRecord(value['error']) ? value['error'] : null;
    const detailsRecord = errorRecord && isOperationErrorRecord(errorRecord['details']) ? errorRecord['details'] : null;
    return normalizeTaskId(detailsRecord ? detailsRecord['task_id'] : null);
};

class TaskFailureError extends Error {
    readonly taskId: string | null;
    readonly status: string | null;
    readonly code: string | null;
    readonly errorCode: number | null;
    readonly errorMessage: string | null;
    readonly errorType: string | null;
    readonly payload?: OperationErrorValue;

    constructor(message: string, metadata: TaskFailureMetadata = {}) {
        super(message || 'Task failed');
        this.name = 'TaskFailureError';
        this.taskId = normalizeTaskId(metadata.taskId);
        this.status = normalizeErrorMessage(metadata.status);
        this.code = normalizeErrorMessage(metadata.code);
        this.errorCode = normalizeErrorCode(metadata.errorCode);
        this.errorMessage = normalizeErrorMessage(metadata.errorMessage);
        this.errorType = normalizeErrorMessage(metadata.errorType);
        if (metadata.payload !== undefined) {
            this.payload = metadata.payload;
        }
    }
}

const isOfflinePolicyCode = (code: string | null): boolean => code === 'offline_mode' || code === 'network_policy_violation';

const isOfflinePolicyStatus = (status: number | null, code: string | null): boolean => status === 423 && code !== 'file_in_use';

const isOfflinePolicyMessage = (message: string): boolean => {
    const normalizedMessage = toTrimmedLower(message);
    return normalizedMessage.includes('stay_offline');
};

const normalizeOperationError = <T>(value: T): NormalizedOperationError | null => {
    if (value instanceof APIError) {
        const taskId = normalizeTaskId(value.taskId) || readNestedTaskId(value.payload);
        const code = normalizeErrorMessage(value.code);
        const message = normalizeErrorMessage(value.message) || normalizeErrorMessage(value.detail) || 'Request failed';
        const status = normalizeErrorCode(value.status);
        const isOfflinePolicy = isOfflinePolicyCode(code) || isOfflinePolicyStatus(status, code) || isOfflinePolicyMessage(message);
        const isInsufficientDiskSpace = code === 'insufficient_disk_space' || status === 507;
        return {
            taskId,
            code,
            status,
            message,
            errorCode: status,
            errorMessage: normalizeErrorMessage(value.message),
            isOfflinePolicy,
            isInsufficientDiskSpace
        };
    }
    if (value instanceof TaskFailureError) {
        const code = normalizeErrorMessage(value.code) || normalizeErrorMessage(value.errorType);
        const errorCode = normalizeErrorCode(value.errorCode);
        const errorMessage = normalizeErrorMessage(value.errorMessage);
        const message = normalizeErrorMessage(value.message) || errorMessage || 'Task failed';
        return {
            taskId: normalizeTaskId(value.taskId),
            code,
            status: null,
            message,
            errorCode,
            errorMessage,
            isOfflinePolicy: isOfflinePolicyCode(code) || isOfflinePolicyStatus(errorCode, code) || isOfflinePolicyMessage(message),
            isInsufficientDiskSpace: code === 'insufficient_disk_space' || errorCode === 507
        };
    }
    if (!isOperationErrorRecord(value)) {
        return null;
    }
    const errorRecord = isOperationErrorRecord(value['error']) ? value['error'] : null;
    const taskId = normalizeTaskId(value['task_id']) || readNestedTaskId(value);
    const code = normalizeErrorMessage(value['code']) || normalizeErrorMessage(value['error_type']) || normalizeErrorMessage(errorRecord ? errorRecord['type'] : null);
    const errorCode = normalizeErrorCode(value['error_code']);
    const errorMessage = normalizeErrorMessage(value['error_message']);
    const message = normalizeErrorMessage(value['message']) || errorMessage || normalizeErrorMessage(errorRecord ? errorRecord['message'] : null) || normalizeErrorMessage(value['error']) || 'Operation failed';
    const status = normalizeErrorCode(value['status']);
    const isOfflinePolicy = isOfflinePolicyCode(code) || isOfflinePolicyStatus(errorCode, code) || isOfflinePolicyStatus(status, code) || isOfflinePolicyMessage(message);
    const isInsufficientDiskSpace = code === 'insufficient_disk_space' || errorCode === 507 || status === 507;
    return {
        taskId,
        code,
        status,
        message,
        errorCode,
        errorMessage,
        isOfflinePolicy,
        isInsufficientDiskSpace
    };
};

const markHandledOperationTask = (taskId: string | null): void => {
    const normalizedTaskId = normalizeTaskId(taskId);
    if (!normalizedTaskId) {
        return;
    }
    pruneTimestampMap(handledTaskIds, HANDLED_TASK_TTL_MS);
    handledTaskIds.set(normalizedTaskId, Date.now());
};

const hasHandledOperationTask = (taskId: string | null): boolean => {
    const normalizedTaskId = normalizeTaskId(taskId);
    if (!normalizedTaskId) {
        return false;
    }
    pruneTimestampMap(handledTaskIds, HANDLED_TASK_TTL_MS);
    return handledTaskIds.has(normalizedTaskId);
};

const buildHandledErrorSignature = (normalized: NormalizedOperationError, publicMessage: string): string | null => {
    const message = normalizeErrorMessage(normalized.message);
    if (!message) {
        return null;
    }
    return `${normalized.code ?? ''}:${normalized.status ?? ''}:${normalized.errorCode ?? ''}:${message}:${publicMessage}`;
};

const markHandledOperationSignature = (signature: string | null): void => {
    if (!signature) {
        return;
    }
    pruneTimestampMap(handledErrorSignatures, HANDLED_ERROR_SIGNATURE_TTL_MS);
    handledErrorSignatures.set(signature, Date.now());
};

const hasHandledOperationSignature = (signature: string | null): boolean => {
    if (!signature) {
        return false;
    }
    pruneTimestampMap(handledErrorSignatures, HANDLED_ERROR_SIGNATURE_TTL_MS);
    return handledErrorSignatures.has(signature);
};

const resolveNormalizedOperationCause = <T>(normalized: NormalizedOperationError | null, value: T): string | null => resolveSkillErrorMessage(normalized?.code, value) ?? resolveOperationCauseMessage(normalized?.code ?? null, value);

const resolveHandledOperationCause = <T>(value: T): string | null => resolveNormalizedOperationCause(normalizeOperationError(value), value);

const notifyHandledOperationError = <T>(value: T): boolean => {
    const normalized = normalizeOperationError(value);
    const causeMessage = resolveNormalizedOperationCause(normalized, value);
    if (!normalized || (!causeMessage && !normalized.isInsufficientDiskSpace && !normalized.isOfflinePolicy)) {
        return false;
    }
    const message = normalizeErrorMessage(normalized.message);
    if (!message) {
        return false;
    }
    if (normalized.taskId && hasHandledOperationTask(normalized.taskId)) {
        return true;
    }
    const publicMessage = causeMessage ?? (normalized.isInsufficientDiskSpace ? i18n.t('common.errors.insufficientDiskSpace') : i18n.t('common.errors.offlinePolicy'));
    const signature = normalized.taskId ? null : buildHandledErrorSignature(normalized, publicMessage);
    if (hasHandledOperationSignature(signature)) {
        return true;
    }
    markHandledOperationTask(normalized.taskId);
    markHandledOperationSignature(signature);
    const reportedSpeechReason = readSpeechSetupReason(readApiErrorDetail(value, 'reason'));
    const voiceSpeech = readApiErrorDetail(value, 'speech_scope') === 'voice';
    if (normalized.code === 'transcription_model_unavailable' && (reportedSpeechReason !== null || voiceSpeech)) {
        const selector = readApiErrorDetail(value, 'selector');
        const speechReason = resolveObservedSpeechReason(reportedSpeechReason, voiceSpeech ? 'voice' : 'media');
        void notifyObservedSpeechOutcome(publicMessage, normalized.taskId ?? signature ?? publicMessage, speechReason, typeof selector === 'string' ? selector : '', voiceSpeech ? 'voice' : 'media').catch((error) => errorHandler.warn('SpeechSetup', 'Speech setup notification could not be shown', ensureError(error)));
        return true;
    }
    if (normalized.code === 'text_to_speech_model_unavailable') {
        void notifyObservedSpeechOutcome(publicMessage, normalized.taskId ?? signature ?? publicMessage, resolveObservedSpeechReason(null, 'synthesis'), 'auto', 'synthesis').catch((error) => errorHandler.warn('SpeechSetup', 'Speech setup notification could not be shown', ensureError(error)));
        return true;
    }
    showNotification(publicMessage, 'error', 6000);
    return true;
};

const createTaskFailureError = <T>(payload: T, defaultMessage: string): TaskFailureError => {
    const record = isOperationErrorRecord(payload) ? payload : null;
    const message = normalizeErrorMessage(record ? record['message'] : null) || normalizeErrorMessage(record ? record['error_message'] : null) || toTrimmedString(defaultMessage) || 'Task failed';
    return new TaskFailureError(message, {
        taskId: normalizeTaskId(record ? record['task_id'] : null),
        status: normalizeErrorMessage(record ? record['status'] : null),
        code: normalizeErrorMessage(record ? record['code'] : null),
        errorCode: normalizeErrorCode(record ? record['error_code'] : null),
        errorMessage: normalizeErrorMessage(record ? record['error_message'] : null),
        errorType: normalizeErrorMessage(record ? record['error_type'] : null),
        payload: isOperationErrorValue(payload) ? payload : undefined
    });
};

class OperationErrorNotifier {
    readonly #tasks: Pick<StreamTaskRuntime, 'subscribeTerminalTasks'>;
    #unsubscribe: (() => void) | null = null;

    constructor(tasks: Pick<StreamTaskRuntime, 'subscribeTerminalTasks'>) {
        this.#tasks = tasks;
    }

    initialize(): void {
        if (this.#unsubscribe) {
            return;
        }
        const listener: TaskTerminalListener = (event: TaskTerminalEvent): void => {
            if (event.success) {
                const result = event['result'];
                if (isJsonObject(result) && Array.isArray(result['missing_capabilities']) && result['missing_capabilities'].includes('speech_to_text')) {
                    void notifyObservedSpeechOutcome(i18n.t('speechSetup.notTranscribedNotice'), event.taskId, null, 'auto', 'media', i18n.t('speechSetup.notTranscribedAskAdministrator')).catch((error) => errorHandler.warn('SpeechSetup', 'Speech setup notification could not be shown', ensureError(error)));
                }
                return;
            }
            notifyHandledOperationError(
                new TaskFailureError(event.message, {
                    taskId: event.taskId,
                    status: event.status,
                    errorCode: event.errorCode ?? null,
                    errorMessage: event.errorMessage ?? null,
                    errorType: event.errorType ?? null,
                    payload: event
                })
            );
        };
        this.#unsubscribe = this.#tasks.subscribeTerminalTasks(listener);
    }

    dispose(): void {
        if (!this.#unsubscribe) {
            return;
        }
        this.#unsubscribe();
        this.#unsubscribe = null;
    }
}

export { OperationErrorNotifier, TaskFailureError, createTaskFailureError, hasHandledOperationTask, markHandledOperationTask, normalizeOperationError, notifyHandledOperationError, resolveHandledOperationCause };
export type { NormalizedOperationError, TaskFailureMetadata };

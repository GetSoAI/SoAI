/* SoAI - Shared tasks tracked task stream [frontend/assets/ts/core/tasks/trackedTaskStream.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { createTaskFailureError } from '@core/operationErrorNotifier.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import { isCancelledTaskStatus } from '@core/tasks/operationPayloads.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

interface TrackedTaskStreamTracker {
    track: (key: string, handle: StreamActionHandle) => void;
    release: (key: string) => void;
}

interface TrackedTaskStreamSettlementOptions {
    tracker: TrackedTaskStreamTracker;
    stream: StreamActionHandle;
    keyPrefix: string;
    failMessage: string;
    keySeparator?: '.' | '-';
}

interface TrackedTaskStreamSettlement {
    record: JsonObject | null;
    cancelled: boolean;
    detached: boolean;
    isCompleteEvent: boolean;
    message: string;
}

const normalizeTrackedTaskStreamRecord = <T>(payload: T): JsonObject | null => {
    return isJsonObject(payload) ? payload : null;
};

const settleTrackedTaskStream = async (options: TrackedTaskStreamSettlementOptions): Promise<TrackedTaskStreamSettlement> => {
    const key = generateSecureId({
        prefix: options.keyPrefix,
        separator: options.keySeparator ?? '-'
    });
    options.tracker.track(key, options.stream);
    try {
        const payload = await options.stream.finished;
        const record = normalizeTrackedTaskStreamRecord(payload);
        const message = toTrimmedString(record?.['message']);
        const status = record?.['status'];
        const cancelled = record?.['cancelled'] === true || isCancelledTaskStatus(isString(status) ? status : undefined);
        const detached = record?.['detached'] === true;
        if (!cancelled && !detached && record?.['success'] === false) {
            throw createTaskFailureError(record, options.failMessage);
        }
        return {
            record,
            cancelled,
            detached,
            isCompleteEvent: record?.['type'] === 'TaskCompleteEvent',
            message
        };
    } finally {
        options.tracker.release(key);
    }
};

export { normalizeTrackedTaskStreamRecord, settleTrackedTaskStream };
export type { TrackedTaskStreamSettlement, TrackedTaskStreamSettlementOptions, TrackedTaskStreamTracker };

/* SoAI - Task-to-operation progress adaptation [frontend/assets/ts/core/operationprogress/taskProgressAdapter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationProgressData } from '@core/operationprogress/types.ts';
import { resolveOperationProgressDetails } from '@core/operationprogress/transferDetails.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';

const readProgressValue = (payload: JsonValue | null | undefined): number | undefined => {
    if (!isObject(payload)) {
        return undefined;
    }
    const progress = payload['progress'];
    if (isFiniteNumber(progress)) {
        return normalizeProgressPercent(progress) ?? 0;
    }
    const percent = payload['percent'];
    if (isFiniteNumber(percent)) {
        return normalizeProgressPercent(percent) ?? 0;
    }
    return undefined;
};

const taskProgressPayloadToOperationProgress = (payload: JsonValue | null | undefined): OperationProgressData => {
    if (!isObject(payload)) {
        return { state: 'downloading' };
    }
    const data: OperationProgressData = { state: 'downloading' };
    const progress = readProgressValue(payload);
    if (progress !== undefined) {
        data.progress = progress;
    }
    const message = payload['message'];
    if (isString(message)) {
        data.message = message;
    }
    const details = resolveOperationProgressDetails(payload);
    if (details) {
        data.details = details;
    }
    return data;
};

export { taskProgressPayloadToOperationProgress };

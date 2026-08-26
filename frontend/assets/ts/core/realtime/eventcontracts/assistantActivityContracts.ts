/* SoAI - Frontend assistant activity payload contracts [frontend/assets/ts/core/realtime/eventcontracts/assistantActivityContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantActivityState } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { isNonNegativeInteger, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const decodeAssistantActivity = (value: JsonValue | null | undefined): AssistantActivityState | null => {
    if (!isObject(value)) return null;
    const status = value['status'];
    const startedAtMs = value['started_at_ms'];
    const durationMs = value['duration_ms'];
    if (!isString(status) || (status !== 'running' && status !== 'completed' && status !== 'cancelled' && status !== 'error')) return null;
    if (!isNonNegativeInteger(startedAtMs) || !isNonNegativeInteger(durationMs)) return null;
    const decoded: AssistantActivityState = { status, startedAtMs, durationMs };
    const reason = value['reason'];
    if (isString(reason) && reason.trim()) decoded.reason = reason.trim();
    const errorType = value['error_type'];
    if (isString(errorType) && errorType.trim()) decoded.errorType = errorType.trim();
    return decoded;
};

export { decodeAssistantActivity };

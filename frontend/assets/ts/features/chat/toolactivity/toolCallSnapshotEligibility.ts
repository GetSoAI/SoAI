/* SoAI - Persisted tool call snapshot eligibility policy [frontend/assets/ts/features/chat/toolactivity/toolCallSnapshotEligibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isSubagentParentToolCallId } from '@features/chat/agent/subagentCallIds.ts';
import { isSubagentChildToolCallId } from '@features/chat/message/messageview/subagentToolCallSegments.ts';

const canRequestPersistedToolCallSnapshot = (callId: string): boolean => {
    const normalizedCallId = toTrimmedString(callId);
    return Boolean(normalizedCallId) && !isSubagentParentToolCallId(normalizedCallId) && !isSubagentChildToolCallId(normalizedCallId);
};

export { canRequestPersistedToolCallSnapshot };

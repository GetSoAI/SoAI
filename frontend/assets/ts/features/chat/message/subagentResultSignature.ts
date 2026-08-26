/* SoAI - Chat feature subagent result signature [frontend/assets/ts/features/chat/message/subagentResultSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { resolveSegmentSignature } from '@features/chat/message/messageSegmentSignatures.ts';
import { resolveSubagentToolResultModel } from '@features/chat/message/messageview/subagentStreamSegments.ts';

const resolveSubagentResultSignature = (result: JsonValue): string => {
    const model = resolveSubagentToolResultModel(result, 'subagent-signature', {
        assistantTurnTimestamp: 0,
        modelVariantIndex: 0
    });
    const signatures: string[] = [];
    const nowMs = serverEpochMs();
    for (const segment of model.streamSegments) {
        signatures.push(resolveSegmentSignature(segment, nowMs));
    }
    return stableJsonStringify(['subagent', model.resultText, model.streamSegments.length, signatures]);
};

export { resolveSubagentResultSignature };

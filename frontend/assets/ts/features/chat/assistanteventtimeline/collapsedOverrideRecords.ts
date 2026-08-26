/* SoAI - Chat feature collapsed override records [frontend/assets/ts/features/chat/assistanteventtimeline/collapsedOverrideRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isObject } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

type CollapsedOverrideFieldName = 'inlineThinkingCollapsedByCallId' | 'inlineToolCollapsedByCallId';

const cloneCollapsedOverrideRecord = (value: JsonValue | null | undefined): Record<string, boolean> | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const clone: Record<string, boolean> = {};
    for (const [rawCallId, rawCollapsed] of Object.entries(value)) {
        const callId = rawCallId.trim();
        if (!callId || !isBoolean(rawCollapsed)) {
            continue;
        }
        clone[callId] = rawCollapsed;
    }
    return Object.keys(clone).length > 0 ? clone : null;
};

const preserveCollapsedOverrideRecordField = (source: ChatMessage, target: ChatMessage, fieldName: CollapsedOverrideFieldName): void => {
    const sourceRecord = cloneCollapsedOverrideRecord(source[fieldName]);
    if (sourceRecord) {
        target[fieldName] = sourceRecord;
        return;
    }
    const targetRecord = cloneCollapsedOverrideRecord(target[fieldName]);
    if (targetRecord) {
        target[fieldName] = targetRecord;
        return;
    }
    delete target[fieldName];
};

const preserveAssistantCollapsedOverrideRecords = (source: ChatMessage, target: ChatMessage): void => {
    preserveCollapsedOverrideRecordField(source, target, 'inlineThinkingCollapsedByCallId');
    preserveCollapsedOverrideRecordField(source, target, 'inlineToolCollapsedByCallId');
};

export { cloneCollapsedOverrideRecord, preserveAssistantCollapsedOverrideRecords };
export type { CollapsedOverrideFieldName };

/* SoAI - Owner-private skill revision event contracts [frontend/assets/ts/core/realtime/eventcontracts/skillContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireSkillRevision } from '@core/api/contracts/webuiSkillContracts.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredNonEmptyStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface SkillLibraryChangedEvent {
    userId: number;
    revision: number;
}

interface ConversationSkillsChangedEvent extends SkillLibraryChangedEvent {
    conversationId: string;
}

const decodeLibraryChanged = (payload: JsonValue): SkillLibraryChangedEvent => {
    const record = requireRecord(payload, 'Skill library event');
    return { userId: readRequiredPositiveIntegerValue(record['user_id'], 'Skill owner'), revision: requireSkillRevision(record['revision']) };
};

const decodeSelectionChanged = (payload: JsonValue): ConversationSkillsChangedEvent => {
    const record = requireRecord(payload, 'Skill selection event');
    return { ...decodeLibraryChanged(payload), conversationId: readRequiredNonEmptyStringValue(record['conv_id'], 'Skill conversation') };
};

const SKILL_EVENT_CONTRACTS = Object.freeze({
    libraryChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.SKILL_LIBRARY_CHANGED, decodeLibraryChanged),
    selectionChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_SKILLS_CHANGED, decodeSelectionChanged)
});

export { SKILL_EVENT_CONTRACTS };
export type { ConversationSkillsChangedEvent, SkillLibraryChangedEvent };

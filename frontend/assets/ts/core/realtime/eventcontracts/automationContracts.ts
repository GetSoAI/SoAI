/* SoAI - Frontend automation WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/automationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredFiniteNumberValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface AutomationChangedEvent {
    eventId: string;
    timestamp: number;
    userId: number;
    automationId: string;
}

interface AutomationRunChangedEvent extends AutomationChangedEvent {
    runId: string;
}

const decodeAutomationChangedEvent = (payload: JsonValue): AutomationChangedEvent => {
    const record = requireRecord(payload, 'Automation event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Automation event.timestamp');
    if (timestamp <= 0) throw new TypeError('Automation event.timestamp must be positive');
    return {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Automation event.event_id'),
        timestamp,
        userId: readRequiredPositiveIntegerValue(record['user_id'], 'Automation event.user_id'),
        automationId: readRequiredTrimmedStringValue(record['automation_id'], 'Automation event.automation_id')
    };
};

const decodeAutomationRunChangedEvent = (payload: JsonValue): AutomationRunChangedEvent => {
    const record = requireRecord(payload, 'Automation run event');
    return { ...decodeAutomationChangedEvent(payload), runId: readRequiredTrimmedStringValue(record['run_id'], 'Automation run event.run_id') };
};

const AUTOMATION_EVENT_CONTRACTS = Object.freeze({
    created: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AUTOMATION_CREATED, decodeAutomationChangedEvent),
    updated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AUTOMATION_UPDATED, decodeAutomationChangedEvent),
    deleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AUTOMATION_DELETED, decodeAutomationChangedEvent),
    runCreated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AUTOMATION_RUN_CREATED, decodeAutomationRunChangedEvent),
    runUpdated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AUTOMATION_RUN_UPDATED, decodeAutomationRunChangedEvent)
});

export { AUTOMATION_EVENT_CONTRACTS };
export type { AutomationChangedEvent, AutomationRunChangedEvent };

/* SoAI - Frontend notification WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/notificationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseNotificationCreatedToast, type NotificationCreatedToast } from '@core/notifications/toastParsing.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonArray, type JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface NotificationIdentifiersEvent {
    notificationIds: string[];
}

const decodeNotificationCreated = (payload: JsonValue): NotificationCreatedToast => {
    const decoded = parseNotificationCreatedToast(payload);
    if (decoded === null) throw new TypeError('Notification created event payload is invalid');
    return decoded;
};

const normalizeNotificationIds = (values: readonly JsonValue[]): string[] => {
    const notificationIds: string[] = [];
    for (const value of values) {
        if (!isString(value)) throw new TypeError('Notification identifier must be a string');
        const notificationId = value.trim();
        if (notificationId && !notificationIds.includes(notificationId)) notificationIds.push(notificationId);
    }
    return notificationIds;
};

const decodeNotificationsMarkedRead = (payload: JsonValue): NotificationIdentifiersEvent => {
    const record = requireRecord(payload, 'Notifications marked-read event');
    const values = record['notification_ids'];
    if (!isJsonArray(values)) throw new TypeError('Notifications marked-read event.notification_ids must be an array');
    return { notificationIds: normalizeNotificationIds(values) };
};

const decodeNotificationDeleted = (payload: JsonValue): NotificationIdentifiersEvent => {
    const record = requireRecord(payload, 'Notification deleted event');
    return { notificationIds: normalizeNotificationIds([record['notification_id'] ?? null]) };
};

const NOTIFICATION_EVENT_CONTRACTS = Object.freeze({
    created: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.NOTIFICATION_CREATED, decodeNotificationCreated),
    markedRead: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.NOTIFICATIONS_MARKED_READ, decodeNotificationsMarkedRead),
    deleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.NOTIFICATION_DELETED, decodeNotificationDeleted)
});

export { NOTIFICATION_EVENT_CONTRACTS };
export type { NotificationIdentifiersEvent };

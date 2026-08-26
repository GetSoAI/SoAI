/* SoAI - Shared notifications list parsing [frontend/assets/ts/core/notifications/listParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseNotificationText } from '@core/notifications/textParsing.ts';
import type { NotificationCursor, NotificationRecord, NotificationsListResponse } from '@core/notifications/types.ts';
import { assertAllowedNotificationKeys, parseNotificationLink, parseNotificationRecordType } from '@core/notifications/valueParsing.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';

const NOTIFICATION_RECORD_KEYS: ReadonlySet<string> = Object.freeze(new Set(['id', 'user_id', 'created_at_ms', 'type', 'title', 'message', 'source', 'link', 'read_at_ms']));
const NOTIFICATION_CURSOR_KEYS: ReadonlySet<string> = Object.freeze(new Set(['created_at_ms', 'id']));
const NOTIFICATIONS_LIST_KEYS: ReadonlySet<string> = Object.freeze(new Set(['notifications', 'total_count', 'unread_count', 'next_cursor']));
const NOTIFICATION_STATE_RECORD_KEYS: ReadonlySet<string> = Object.freeze(new Set(['id', 'userId', 'createdAtMs', 'type', 'title', 'message', 'source', 'link', 'readAtMs']));
const NOTIFICATION_STATE_CURSOR_KEYS: ReadonlySet<string> = Object.freeze(new Set(['createdAtMs', 'id']));
const NOTIFICATION_STATE_LIST_KEYS: ReadonlySet<string> = Object.freeze(new Set(['notifications', 'totalCount', 'unreadCount', 'nextCursor']));
const NOTIFICATION_STATE_TEXT_KEYS: ReadonlySet<string> = Object.freeze(new Set(['textType', 'text', 'template', 'parameters']));
const NOTIFICATION_STATE_LINK_KEYS: ReadonlySet<string> = Object.freeze(new Set(['linkType', 'value']));

const parseNotificationCursor = (value: JsonValue | null | undefined, strict: boolean): NotificationCursor | null => {
    if (value == null) {
        return null;
    }
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications next_cursor must be an object or null');
    }
    if (strict) {
        assertAllowedNotificationKeys(value, NOTIFICATION_CURSOR_KEYS, 'webui.notifications next_cursor');
    }
    const createdAtValue = value['created_at_ms'];
    const idValue = value['id'];
    if (!isNumber(createdAtValue) || !Number.isInteger(createdAtValue) || createdAtValue < 1) {
        throw new TypeError('webui.notifications next_cursor created_at_ms must be a positive integer');
    }
    if (!isString(idValue) || !idValue.trim()) {
        throw new TypeError('webui.notifications next_cursor id must be a non-empty string');
    }
    return { createdAtMs: createdAtValue, id: idValue.trim() };
};

const parseNotificationRecord = (value: JsonValue | null | undefined, strict: boolean): NotificationRecord => {
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications notification entry must be an object');
    }
    if (strict) {
        assertAllowedNotificationKeys(value, NOTIFICATION_RECORD_KEYS, 'webui.notifications notification entry');
    }
    const idValue = value['id'];
    const userIdValue = value['user_id'];
    const createdValue = value['created_at_ms'];
    const typeValue = parseNotificationRecordType(value['type']);
    const sourceValue = value['source'];
    const readAtValue = value['read_at_ms'];
    if (!isString(idValue) || !idValue.trim()) {
        throw new TypeError('webui.notifications notification entry id must be a non-empty string');
    }
    if (!isNumber(userIdValue) || !Number.isInteger(userIdValue) || userIdValue < 1) {
        throw new TypeError('webui.notifications notification entry user_id must be a positive integer');
    }
    if (!isNumber(createdValue) || !Number.isInteger(createdValue) || createdValue < 1) {
        throw new TypeError('webui.notifications notification entry created_at_ms must be a positive integer');
    }
    if (typeValue === null) {
        throw new TypeError('webui.notifications notification entry type is invalid');
    }
    if (sourceValue != null && (!isString(sourceValue) || !sourceValue.trim())) {
        throw new TypeError('webui.notifications notification entry source must be a non-empty string or null');
    }
    if (readAtValue != null && (!isNumber(readAtValue) || !Number.isInteger(readAtValue) || readAtValue < 1)) {
        throw new TypeError('webui.notifications notification entry read_at_ms must be a positive integer or null');
    }
    return {
        id: idValue.trim(),
        userId: userIdValue,
        createdAtMs: createdValue,
        type: typeValue,
        title: parseNotificationText(value['title'], { strict, label: 'webui.notifications notification entry title' }),
        message: parseNotificationText(value['message'], { strict, label: 'webui.notifications notification entry message' }),
        source: sourceValue == null ? null : sourceValue.trim(),
        link: parseNotificationLink(value['link'], { strict, label: 'webui.notifications notification link' }),
        readAtMs: readAtValue == null ? null : readAtValue
    };
};

const parseStrictNotificationRecord = (value: JsonValue | null | undefined): NotificationRecord => parseNotificationRecord(value, true);

const parseStrictNotificationsListResponse = (value: JsonValue | null | undefined): NotificationsListResponse => {
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications snapshot payload must be an object');
    }
    assertAllowedNotificationKeys(value, NOTIFICATIONS_LIST_KEYS, 'webui.notifications snapshot payload');
    const notificationsValue = value['notifications'];
    const totalValue = value['total_count'];
    const unreadValue = value['unread_count'];
    if (!isArray(notificationsValue)) {
        throw new TypeError('webui.notifications notifications must be an array');
    }
    if (!isNumber(totalValue) || !Number.isInteger(totalValue) || totalValue < 0) {
        throw new TypeError('webui.notifications total_count must be a non-negative integer');
    }
    if (!isNumber(unreadValue) || !Number.isInteger(unreadValue) || unreadValue < 0) {
        throw new TypeError('webui.notifications unread_count must be a non-negative integer');
    }
    if (unreadValue > totalValue) {
        throw new TypeError('webui.notifications unread_count cannot exceed total_count');
    }
    return {
        notifications: notificationsValue.map((entry) => parseNotificationRecord(entry, true)),
        totalCount: totalValue,
        unreadCount: unreadValue,
        nextCursor: parseNotificationCursor(value['next_cursor'], true)
    };
};

const parseNotificationsListResponse = (value: JsonValue | null | undefined): NotificationsListResponse | null => {
    try {
        if (!isPlainObject(value)) {
            return null;
        }
        const notificationsValue = value['notifications'];
        const totalValue = value['total_count'];
        const unreadValue = value['unread_count'];
        if (!isArray(notificationsValue) || !isNumber(totalValue) || !Number.isInteger(totalValue) || totalValue < 0 || !isNumber(unreadValue) || !Number.isInteger(unreadValue) || unreadValue < 0 || unreadValue > totalValue) {
            return null;
        }
        return {
            notifications: notificationsValue.map((entry) => parseNotificationRecord(entry, false)),
            totalCount: totalValue,
            unreadCount: unreadValue,
            nextCursor: parseNotificationCursor(value['next_cursor'], false)
        };
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('NotificationsListParsing', 'Failed to parse notifications list response', runtimeError);
        return null;
    }
};

const parseNotificationStateText = (value: JsonValue | null | undefined, label: string): NotificationRecord['title'] => {
    if (!isPlainObject(value)) {
        throw new TypeError(`${label} must be an object`);
    }
    assertAllowedNotificationKeys(value, NOTIFICATION_STATE_TEXT_KEYS, label);
    if (value['textType'] === 'text') {
        return parseNotificationText({ 'text_type': 'text', text: value['text'] ?? null }, { strict: true, label });
    }
    if (value['textType'] === 'template') {
        const parameters = value['parameters'];
        return parseNotificationText(
            {
                'text_type': 'template',
                template: value['template'] ?? null,
                'params': parameters === undefined ? {} : parameters
            },
            { strict: true, label }
        );
    }
    throw new TypeError(`${label}.textType is invalid`);
};

const parseNotificationStateLink = (value: JsonValue | null | undefined, label: string): NotificationRecord['link'] => {
    if (value == null) {
        return null;
    }
    if (!isPlainObject(value)) {
        throw new TypeError(`${label} must be an object or null`);
    }
    assertAllowedNotificationKeys(value, NOTIFICATION_STATE_LINK_KEYS, label);
    return parseNotificationLink({ 'link_type': value['linkType'] ?? null, value: value['value'] ?? null }, { strict: true, label });
};

const parseNotificationStateCursor = (value: JsonValue | null | undefined): NotificationCursor | null => {
    if (value == null) {
        return null;
    }
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications state nextCursor must be an object or null');
    }
    assertAllowedNotificationKeys(value, NOTIFICATION_STATE_CURSOR_KEYS, 'webui.notifications state nextCursor');
    const createdAtValue = value['createdAtMs'];
    const idValue = value['id'];
    if (!isNumber(createdAtValue) || !Number.isInteger(createdAtValue) || createdAtValue < 1) {
        throw new TypeError('webui.notifications state nextCursor createdAtMs must be a positive integer');
    }
    if (!isString(idValue) || !idValue.trim()) {
        throw new TypeError('webui.notifications state nextCursor id must be a non-empty string');
    }
    return { createdAtMs: createdAtValue, id: idValue.trim() };
};

const parseNotificationStateRecord = (value: JsonValue | null | undefined): NotificationRecord => {
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications state notification entry must be an object');
    }
    assertAllowedNotificationKeys(value, NOTIFICATION_STATE_RECORD_KEYS, 'webui.notifications state notification entry');
    const idValue = value['id'];
    const userIdValue = value['userId'];
    const createdAtValue = value['createdAtMs'];
    const typeValue = parseNotificationRecordType(value['type']);
    const sourceValue = value['source'];
    const readAtValue = value['readAtMs'];
    if (!isString(idValue) || !idValue.trim()) throw new TypeError('webui.notifications state notification entry id must be a non-empty string');
    if (!isNumber(userIdValue) || !Number.isInteger(userIdValue) || userIdValue < 1) throw new TypeError('webui.notifications state notification entry userId must be a positive integer');
    if (!isNumber(createdAtValue) || !Number.isInteger(createdAtValue) || createdAtValue < 1) throw new TypeError('webui.notifications state notification entry createdAtMs must be a positive integer');
    if (typeValue === null) throw new TypeError('webui.notifications state notification entry type is invalid');
    if (sourceValue != null && (!isString(sourceValue) || !sourceValue.trim())) throw new TypeError('webui.notifications state notification entry source must be a non-empty string or null');
    if (readAtValue != null && (!isNumber(readAtValue) || !Number.isInteger(readAtValue) || readAtValue < 1)) throw new TypeError('webui.notifications state notification entry readAtMs must be a positive integer or null');
    return {
        id: idValue.trim(),
        userId: userIdValue,
        createdAtMs: createdAtValue,
        type: typeValue,
        title: parseNotificationStateText(value['title'], 'webui.notifications state notification entry title'),
        message: parseNotificationStateText(value['message'], 'webui.notifications state notification entry message'),
        source: sourceValue == null ? null : sourceValue.trim(),
        link: parseNotificationStateLink(value['link'], 'webui.notifications state notification entry link'),
        readAtMs: readAtValue == null ? null : readAtValue
    };
};

const parseNotificationsListState = (value: JsonValue | null | undefined): NotificationsListResponse => {
    if (!isPlainObject(value)) {
        throw new TypeError('webui.notifications state payload must be an object');
    }
    assertAllowedNotificationKeys(value, NOTIFICATION_STATE_LIST_KEYS, 'webui.notifications state payload');
    const notificationsValue = value['notifications'];
    const totalValue = value['totalCount'];
    const unreadValue = value['unreadCount'];
    if (!isArray(notificationsValue)) throw new TypeError('webui.notifications state notifications must be an array');
    if (!isNumber(totalValue) || !Number.isInteger(totalValue) || totalValue < 0) throw new TypeError('webui.notifications state totalCount must be a non-negative integer');
    if (!isNumber(unreadValue) || !Number.isInteger(unreadValue) || unreadValue < 0) throw new TypeError('webui.notifications state unreadCount must be a non-negative integer');
    if (unreadValue > totalValue) throw new TypeError('webui.notifications state unreadCount cannot exceed totalCount');
    return {
        notifications: notificationsValue.map(parseNotificationStateRecord),
        totalCount: totalValue,
        unreadCount: unreadValue,
        nextCursor: parseNotificationStateCursor(value['nextCursor'])
    };
};

export { parseNotificationsListResponse, parseNotificationsListState, parseStrictNotificationRecord, parseStrictNotificationsListResponse };

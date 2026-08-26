/* SoAI - Shared notifications value parsing [frontend/assets/ts/core/notifications/valueParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationLink, NotificationLinkType, NotificationRecordType } from '@core/notifications/types.ts';
import { isPlainObject, isString } from '@core/typeGuards.ts';

const NOTIFICATION_LINK_KEYS: ReadonlySet<string> = Object.freeze(new Set(['link_type', 'value']));

const assertAllowedNotificationKeys = (value: Record<string, JsonValue>, allowed: ReadonlySet<string>, label: string): void => {
    for (const key of Object.keys(value)) {
        if (!allowed.has(key)) {
            throw new TypeError(`${label} includes unsupported field: ${key}`);
        }
    }
};

const parseNotificationRecordType = (value: JsonValue | undefined): NotificationRecordType | null => {
    if (value === 'info' || value === 'success' || value === 'warning' || value === 'error') {
        return value;
    }
    return null;
};

const parseNotificationLinkType = (value: JsonValue | undefined): NotificationLinkType | null => {
    if (value === 'url' || value === 'conversation' || value === 'automation_run') {
        return value;
    }
    return null;
};

const parseNotificationLink = (value: JsonValue | undefined, options: { strict: boolean; label: string }): NotificationLink | null => {
    if (value == null) {
        return null;
    }
    if (!isPlainObject(value)) {
        throw new TypeError(`${options.label} must be an object or null`);
    }
    if (options.strict) {
        assertAllowedNotificationKeys(value, NOTIFICATION_LINK_KEYS, options.label);
    }
    const linkType = parseNotificationLinkType(value['link_type']);
    if (linkType === null) {
        throw new TypeError(`${options.label}.link_type is invalid`);
    }
    const linkValue = value['value'];
    if (!isString(linkValue) || !linkValue.trim()) {
        throw new TypeError(`${options.label}.value must be a non-empty string`);
    }
    return { linkType: linkType, value: linkValue.trim() };
};

export { assertAllowedNotificationKeys, parseNotificationLink, parseNotificationLinkType, parseNotificationRecordType };

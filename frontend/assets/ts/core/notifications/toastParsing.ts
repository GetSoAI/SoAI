/* SoAI - Shared notifications toast parsing [frontend/assets/ts/core/notifications/toastParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseNotificationText } from '@core/notifications/textParsing.ts';
import { resolveNotificationText } from '@core/notifications/textResolution.ts';
import type { NotificationLink, NotificationRecordType, NotificationText } from '@core/notifications/types.ts';
import { parseNotificationLink, parseNotificationRecordType } from '@core/notifications/valueParsing.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type NotificationCreatedToast = {
    notificationId: string;
    type: NotificationRecordType;
    resolvedMessage: string;
    titleText: NotificationText;
    messageText: NotificationText;
    link: NotificationLink | null;
};

const parseNotificationCreatedToast = (payload: JsonValue): NotificationCreatedToast => {
    if (!isPlainObject(payload)) {
        throw new Error('webui.notifications created event payload must be an object');
    }
    const parsedType = parseNotificationRecordType(payload['notification_type']);
    if (parsedType === null) {
        throw new Error('webui.notifications created event notification_type is invalid');
    }
    const title = parseNotificationText(payload['title'], { strict: false, label: 'webui.notifications created event title' });
    const message = parseNotificationText(payload['message'], { strict: false, label: 'webui.notifications created event message' });
    return {
        notificationId: typeof payload['notification_id'] === 'string' ? payload['notification_id'].trim() : '',
        type: parsedType,
        resolvedMessage: `${resolveNotificationText(title)}: ${resolveNotificationText(message)}`,
        titleText: title,
        messageText: message,
        link: parseNotificationLink(payload['link'], { strict: false, label: 'webui.notifications created event link' })
    };
};

export { parseNotificationCreatedToast };
export type { NotificationCreatedToast };

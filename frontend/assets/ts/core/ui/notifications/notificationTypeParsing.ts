/* SoAI - Shared frontend UI notifications notification type parsing [frontend/assets/ts/core/ui/notifications/notificationTypeParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

type StandardNotificationType = 'success' | 'error' | 'warning' | 'info';

const isNotificationType = (value: JsonValue): value is NotificationType => value === 'success' || value === 'error' || value === 'warning' || value === 'danger' || value === 'info' || value === 'copy' || value === 'refresh' || value === 'download';

const isStandardNotificationType = (value: JsonValue): value is StandardNotificationType => value === 'success' || value === 'error' || value === 'warning' || value === 'info';

const parseNotificationType = (value: JsonValue): NotificationType => {
    if (isNotificationType(value)) {
        return value;
    }
    throw new Error(`Invalid notification type: ${String(value)}`);
};

const parseStandardNotificationType = (value: JsonValue): StandardNotificationType => {
    if (isStandardNotificationType(value)) {
        return value;
    }
    throw new Error(`Invalid notification type: ${String(value)}`);
};

export { isNotificationType, parseNotificationType, parseStandardNotificationType };
export type { StandardNotificationType };

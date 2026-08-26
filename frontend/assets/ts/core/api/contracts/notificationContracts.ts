/* SoAI - Frontend notification API contracts [frontend/assets/ts/core/api/contracts/notificationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { parseStrictNotificationRecord } from '@core/notifications/listParsing.ts';
import type { NotificationRecord } from '@core/notifications/types.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';

const decodeNotificationRecord = (value: ApiResponsePayload): NotificationRecord => {
    if (!isJsonValue(value)) throw new TypeError('Notification response must be JSON');
    return parseStrictNotificationRecord(value);
};

export { decodeNotificationRecord };
export type { NotificationRecord };

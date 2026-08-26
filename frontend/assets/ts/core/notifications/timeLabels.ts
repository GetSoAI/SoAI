/* SoAI - Shared notifications time labels [frontend/assets/ts/core/notifications/timeLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatDateTimeSecond } from '@core/primitives/dateTime.ts';

const resolveNotificationTimeLabel = (createdAtMs: number): string => {
    if (!Number.isFinite(createdAtMs) || createdAtMs <= 0) {
        return '';
    }
    return formatDateTimeSecond(createdAtMs);
};

export { resolveNotificationTimeLabel };

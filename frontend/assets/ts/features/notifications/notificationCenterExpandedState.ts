/* SoAI - Notifications feature notification center expanded state [frontend/assets/ts/features/notifications/notificationCenterExpandedState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationsListResponse } from '@core/notifications/types.ts';

const toggleNotificationExpandedId = (expandedNotificationIds: Set<string>, notificationId: string): boolean => {
    if (expandedNotificationIds.has(notificationId)) {
        expandedNotificationIds.delete(notificationId);
        return false;
    }
    expandedNotificationIds.add(notificationId);
    return true;
};

const synchronizeExpandedNotificationIds = (expandedNotificationIds: Set<string>, snapshot: NotificationsListResponse | null): void => {
    const notifications = snapshot ? snapshot.notifications : [];
    const validIds = new Set<string>(notifications.map((notification) => notification.id));
    for (const expandedId of expandedNotificationIds) {
        if (!validIds.has(expandedId)) {
            expandedNotificationIds.delete(expandedId);
        }
    }
};

export { synchronizeExpandedNotificationIds, toggleNotificationExpandedId };

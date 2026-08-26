/* SoAI - Notifications feature notification center pagination [frontend/assets/ts/features/notifications/notificationCenterPagination.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationRecord, NotificationsListResponse } from '@core/notifications/types.ts';

interface NotificationCenterPagingState {
    headSnapshot: NotificationsListResponse | null;
    olderNotifications: NotificationRecord[];
    nextCursor: NotificationsListResponse['nextCursor'];
    isLoadingMore: boolean;
}

const createNotificationCenterPagingState = (): NotificationCenterPagingState => ({
    headSnapshot: null,
    olderNotifications: [],
    nextCursor: null,
    isLoadingMore: false
});

const setNotificationHeadSnapshot = (state: NotificationCenterPagingState, snapshot: NotificationsListResponse | null, isLoadingMore: boolean): NotificationCenterPagingState => {
    if (snapshot == null) {
        return createNotificationCenterPagingState();
    }
    const headIds = new Set(snapshot.notifications.map((notification) => notification.id));
    const olderNotifications = state.olderNotifications.filter((notification) => !headIds.has(notification.id));
    const nextCursor = olderNotifications.length > 0 ? state.nextCursor : snapshot.nextCursor;
    return {
        ...state,
        headSnapshot: snapshot,
        olderNotifications,
        nextCursor,
        isLoadingMore
    };
};

const appendNotificationHistoryPage = (state: NotificationCenterPagingState, snapshot: NotificationsListResponse): NotificationCenterPagingState => {
    const existingIds = new Set<string>();
    if (state.headSnapshot) {
        for (const notification of state.headSnapshot.notifications) {
            existingIds.add(notification.id);
        }
    }
    for (const notification of state.olderNotifications) {
        existingIds.add(notification.id);
    }
    const olderNotifications = [...state.olderNotifications];
    for (const notification of snapshot.notifications) {
        if (existingIds.has(notification.id)) {
            continue;
        }
        existingIds.add(notification.id);
        olderNotifications.push(notification);
    }
    return {
        ...state,
        olderNotifications,
        nextCursor: snapshot.nextCursor,
        isLoadingMore: false
    };
};

const markNotificationCenterItemsRead = (state: NotificationCenterPagingState, notificationIds: readonly string[], readAtMs: number): NotificationCenterPagingState => {
    const targetIds = new Set(notificationIds);
    if (targetIds.size === 0) {
        return state;
    }
    const markedIds = new Set<string>();
    const markRead = (notification: NotificationRecord): NotificationRecord => {
        if (!targetIds.has(notification.id) || notification.readAtMs != null) {
            return notification;
        }
        markedIds.add(notification.id);
        return { ...notification, readAtMs: readAtMs };
    };
    const headNotifications = state.headSnapshot ? state.headSnapshot.notifications.map((notification) => markRead(notification)) : [];
    const olderNotifications = state.olderNotifications.map((notification) => markRead(notification));
    const unreadCount = state.headSnapshot ? Math.max(state.headSnapshot.unreadCount - markedIds.size, 0) : 0;
    return {
        ...state,
        headSnapshot: state.headSnapshot
            ? {
                  ...state.headSnapshot,
                  notifications: headNotifications,
                  unreadCount: unreadCount
              }
            : null,
        olderNotifications
    };
};

const removeNotificationCenterItem = (state: NotificationCenterPagingState, notificationId: string): NotificationCenterPagingState => {
    if (!notificationId) {
        return state;
    }
    let removedUnreadCount = 0;
    const keepNotification = (notification: NotificationRecord): boolean => {
        if (notification.id !== notificationId) {
            return true;
        }
        removedUnreadCount = notification.readAtMs == null ? 1 : 0;
        return false;
    };
    const headNotifications = state.headSnapshot ? state.headSnapshot.notifications.filter((notification) => keepNotification(notification)) : [];
    const olderNotifications = state.olderNotifications.filter((notification) => keepNotification(notification));
    if (headNotifications.length === (state.headSnapshot?.notifications.length ?? 0) && olderNotifications.length === state.olderNotifications.length) {
        return state;
    }
    return {
        ...state,
        headSnapshot: state.headSnapshot
            ? {
                  ...state.headSnapshot,
                  notifications: headNotifications,
                  totalCount: Math.max(state.headSnapshot.totalCount - 1, 0),
                  unreadCount: Math.max(state.headSnapshot.unreadCount - removedUnreadCount, 0)
              }
            : null,
        olderNotifications
    };
};

const setNotificationHistoryLoading = (state: NotificationCenterPagingState, isLoadingMore: boolean): NotificationCenterPagingState => ({
    ...state,
    isLoadingMore
});

const resetNotificationHistory = (state: NotificationCenterPagingState): NotificationCenterPagingState => ({
    ...state,
    olderNotifications: [],
    nextCursor: state.headSnapshot ? state.headSnapshot.nextCursor : null,
    isLoadingMore: false
});

const getNotificationCenterSnapshot = (state: NotificationCenterPagingState): NotificationsListResponse | null => {
    if (state.headSnapshot == null) {
        return null;
    }
    return {
        notifications: [...state.headSnapshot.notifications, ...state.olderNotifications],
        totalCount: state.headSnapshot.totalCount,
        unreadCount: state.headSnapshot.unreadCount,
        nextCursor: state.nextCursor
    };
};

export { appendNotificationHistoryPage, createNotificationCenterPagingState, getNotificationCenterSnapshot, markNotificationCenterItemsRead, removeNotificationCenterItem, resetNotificationHistory, setNotificationHeadSnapshot, setNotificationHistoryLoading };
export type { NotificationCenterPagingState };

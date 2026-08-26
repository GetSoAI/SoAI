/* SoAI - Notifications feature notification center data controller [frontend/assets/ts/features/notifications/NotificationCenterDataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { notificationsPath } from '@core/api/endpoints/uiPaths.ts';
import type { ApiClient } from '@core/api/service.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseNotificationsListResponse, parseNotificationsListState } from '@core/notifications/listParsing.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { NotificationsListResponse } from '@core/notifications/types.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { WEBUI_NOTIFICATIONS } from '@core/realtime/streammanager/resources/ids.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { appendNotificationHistoryPage, createNotificationCenterPagingState, getNotificationCenterSnapshot, markNotificationCenterItemsRead, removeNotificationCenterItem, resetNotificationHistory, setNotificationHeadSnapshot, setNotificationHistoryLoading } from '@features/notifications/notificationCenterPagination.ts';

type NotificationCenterLoadState = 'loading' | 'ready' | 'unavailable';

interface NotificationCenterSnapshotState {
    status: NotificationCenterLoadState;
    error: Error | null;
}

interface NotificationCenterStreamManager {
    resources: {
        ensureResourceStarted(resource: string, options?: { allowDiscovery?: boolean }): Promise<import('@core/types/jsonValues.ts').JsonValue | null>;
        refresh(resource: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<import('@core/types/jsonValues.ts').JsonValue | null>;
    };
    subscriptions: {
        subscribeResourceState(resource: string, listener: (snapshot: ResourceSnapshot) => void, options?: { immediate?: boolean; ensureStart?: boolean }): () => void;
    };
}

interface NotificationCenterDataControllerDependencies {
    apiClient: ApiClient;
    stream: NotificationCenterStreamManager;
}

class NotificationCenterDataController {
    readonly #dependencies: NotificationCenterDataControllerDependencies;
    #pagingState = createNotificationCenterPagingState();
    #streamManager: NotificationCenterStreamManager | null = null;
    #streamUnsubscribe: (() => void) | null = null;
    #onSnapshotChange: ((snapshot: NotificationsListResponse | null, state: NotificationCenterSnapshotState) => void) | null = null;
    readonly #historyToken = new SequenceToken();
    readonly #headRefreshToken = new SequenceToken();
    readonly #lifecycleToken = new SequenceToken();
    #confirmedDeletedNotificationIds = new Set<string>();

    constructor(dependencies: NotificationCenterDataControllerDependencies) {
        this.#dependencies = dependencies;
    }

    async initialize(onSnapshotChange: (snapshot: NotificationsListResponse | null, state: NotificationCenterSnapshotState) => void): Promise<void> {
        const lifecycleGeneration = this.#lifecycleToken.next();
        this.#onSnapshotChange = onSnapshotChange;
        const manager = this.#dependencies.stream;
        if (!this.#lifecycleToken.isActive(lifecycleGeneration)) {
            return;
        }
        this.#streamManager = manager;
        if (this.#streamUnsubscribe) {
            this.#streamUnsubscribe();
            this.#streamUnsubscribe = null;
        }
        this.#streamUnsubscribe = manager.subscriptions.subscribeResourceState(
            WEBUI_NOTIFICATIONS,
            (snapshot: ResourceSnapshot): void => {
                if (!this.#lifecycleToken.isActive(lifecycleGeneration)) {
                    return;
                }
                if (!isPlainObject(snapshot.value) && snapshot.status === 'ready') {
                    throw new Error('webui.notifications snapshot payload is invalid');
                }
                const status = snapshot.status;
                if (status === 'error' || status === 'disconnected') {
                    const error = snapshot.error instanceof Error ? snapshot.error : ensureError(snapshot.error);
                    const currentSnapshot = getNotificationCenterSnapshot(this.#pagingState);
                    if (currentSnapshot !== null) {
                        return;
                    }
                    this.#emitSnapshot(null, { status: 'unavailable', error });
                    return;
                }
                if (status !== 'ready') {
                    const currentSnapshot = getNotificationCenterSnapshot(this.#pagingState);
                    if (currentSnapshot !== null) {
                        return;
                    }
                    this.#emitSnapshot(null, { status: 'loading', error: null });
                    return;
                }
                const parsedSnapshot = parseNotificationsListState(snapshot.value);
                const filteredSnapshot = this.#filterDeletedNotifications(parsedSnapshot);
                if (this.#pagingState.isLoadingMore) {
                    this.#historyToken.invalidate();
                }
                this.#pagingState = setNotificationHeadSnapshot(this.#pagingState, filteredSnapshot, false);
                this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
            },
            { immediate: true, ensureStart: false }
        );
        void manager.resources.ensureResourceStarted(WEBUI_NOTIFICATIONS, { allowDiscovery: true }).catch((error) => {
            if (!this.#lifecycleToken.isActive(lifecycleGeneration)) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('NotificationCenter', 'Notifications stream readiness failed', runtimeError);
            if (getNotificationCenterSnapshot(this.#pagingState) !== null) {
                return;
            }
            this.#emitSnapshot(null, { status: 'unavailable', error: runtimeError });
        });
    }

    destroy(): void {
        if (this.#streamUnsubscribe) {
            this.#streamUnsubscribe();
            this.#streamUnsubscribe = null;
        }
        this.#streamManager = null;
        this.#pagingState = createNotificationCenterPagingState();
        this.#onSnapshotChange = null;
        this.#historyToken.invalidate();
        this.#headRefreshToken.invalidate();
        this.#lifecycleToken.invalidate();
        this.#confirmedDeletedNotificationIds.clear();
    }

    canLoadMore(): boolean {
        return this.#pagingState.nextCursor != null;
    }

    isLoadingMore(): boolean {
        return this.#pagingState.isLoadingMore;
    }

    markLoadedNotificationsRead(notificationIds: readonly string[]): void {
        this.#pagingState = markNotificationCenterItemsRead(this.#pagingState, notificationIds, serverEpochMs());
        this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
    }

    confirmNotificationDeleted(notificationId: string): void {
        const normalizedNotificationId = notificationId.trim();
        if (!normalizedNotificationId) {
            throw new Error('Notification id is required for delete confirmation');
        }
        this.#confirmedDeletedNotificationIds.add(normalizedNotificationId);
        this.#pagingState = removeNotificationCenterItem(this.#pagingState, normalizedNotificationId);
        this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
    }

    async refreshHead(resetHistory: boolean): Promise<void> {
        if (!this.#streamManager) {
            throw new Error('NotificationCenter stream manager is unavailable');
        }
        const lifecycleGeneration = this.#lifecycleToken.value;
        const headRefreshGeneration = this.#headRefreshToken.next();
        if (resetHistory) {
            this.#historyToken.invalidate();
            this.#pagingState = setNotificationHistoryLoading(this.#pagingState, false);
            this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
        }
        const snapshot = await this.#streamManager.resources.refresh(WEBUI_NOTIFICATIONS, {
            allowDiscovery: true,
            throwOnError: true
        });
        if (!this.#lifecycleToken.isActive(lifecycleGeneration) || !this.#headRefreshToken.isActive(headRefreshGeneration)) {
            return;
        }
        const parsedSnapshot = parseNotificationsListState(snapshot);
        const filteredSnapshot = this.#filterDeletedNotifications(parsedSnapshot);
        this.#pagingState = setNotificationHeadSnapshot(this.#pagingState, filteredSnapshot, false);
        if (resetHistory) {
            this.#confirmedDeletedNotificationIds.clear();
            this.#pagingState = resetNotificationHistory(this.#pagingState);
        }
        this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
    }

    async loadMore(): Promise<void> {
        if (this.#pagingState.isLoadingMore || this.#pagingState.nextCursor == null) {
            return;
        }
        const nextCursor = this.#pagingState.nextCursor;
        if (nextCursor == null) {
            return;
        }
        const historyGeneration = this.#historyToken.value;
        const lifecycleGeneration = this.#lifecycleToken.value;
        this.#pagingState = setNotificationHistoryLoading(this.#pagingState, true);
        this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
        try {
            const payload = await this.#dependencies.apiClient.get(notificationsPath(), {
                query: {
                    limit: 100,
                    'before_created_at_ms': nextCursor.createdAtMs,
                    'before_id': nextCursor.id
                }
            });
            const page = parseNotificationsListResponse(requireJsonResponsePayload(payload, 'Notification history'));
            if (page == null) {
                throw new Error('Notification history response is invalid');
            }
            if (!this.#lifecycleToken.isActive(lifecycleGeneration)) {
                return;
            }
            if (!this.#historyToken.isActive(historyGeneration)) {
                return;
            }
            this.#pagingState = appendNotificationHistoryPage(this.#pagingState, this.#filterDeletedNotifications(page));
        } catch (error) {
            if (!this.#lifecycleToken.isActive(lifecycleGeneration)) {
                return;
            }
            if (!this.#historyToken.isActive(historyGeneration)) {
                return;
            }
            this.#pagingState = setNotificationHistoryLoading(this.#pagingState, false);
            this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
            throw error;
        }
        this.#emitSnapshot(getNotificationCenterSnapshot(this.#pagingState), { status: 'ready', error: null });
    }

    #emitSnapshot(snapshot: NotificationsListResponse | null, state: NotificationCenterSnapshotState): void {
        if (this.#onSnapshotChange) {
            this.#onSnapshotChange(snapshot, state);
        }
    }

    #filterDeletedNotifications(snapshot: NotificationsListResponse): NotificationsListResponse {
        if (this.#confirmedDeletedNotificationIds.size === 0) {
            return snapshot;
        }
        let removedTotalCount = 0;
        let removedUnreadCount = 0;
        const notifications = snapshot.notifications.filter((notification) => {
            if (!this.#confirmedDeletedNotificationIds.has(notification.id)) {
                return true;
            }
            removedTotalCount += 1;
            if (notification.readAtMs == null) {
                removedUnreadCount += 1;
            }
            return false;
        });
        if (removedTotalCount === 0) {
            return snapshot;
        }
        return {
            ...snapshot,
            notifications,
            totalCount: Math.max(snapshot.totalCount - removedTotalCount, 0),
            unreadCount: Math.max(snapshot.unreadCount - removedUnreadCount, 0)
        };
    }
}

export { NotificationCenterDataController };
export type { NotificationCenterDataControllerDependencies, NotificationCenterSnapshotState, NotificationCenterStreamManager };

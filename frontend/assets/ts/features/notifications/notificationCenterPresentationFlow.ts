/* SoAI - Notifications feature notification center presentation flow [frontend/assets/ts/features/notifications/notificationCenterPresentationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationsListResponse } from '@core/notifications/types.ts';
import type { NotificationCenterSnapshotState } from '@features/notifications/NotificationCenterDataController.ts';
import { synchronizeExpandedNotificationIds } from '@features/notifications/notificationCenterExpandedState.ts';
import { NotificationCenterView } from '@features/notifications/NotificationCenterView.ts';
import type { NotificationCenterElements } from '@features/notifications/uiTypes.ts';

const NOTIFICATION_SCROLL_LOAD_THRESHOLD_PX = 64;

interface NotificationCenterSnapshotRenderRequest {
    elements: NotificationCenterElements;
    expandedNotificationIds: Set<string>;
    isDropdownOpen: boolean;
    isLoadingMore: boolean;
    isVisible: boolean;
    snapshot: NotificationsListResponse | null;
    state: NotificationCenterSnapshotState;
}

interface NotificationCenterLoadMoreDependencies {
    canLoadMore: () => boolean;
    isLoadingMore: () => boolean;
    isMarkingRead: () => boolean;
    loadMore: () => void;
}

interface NotificationCenterLoadMoreRequest {
    isDropdownOpen: boolean;
    isExpanded: boolean;
    isVisible: boolean;
    listElement: HTMLElement | null;
}

class NotificationCenterPresentationFlow {
    readonly #loadMoreDependencies: NotificationCenterLoadMoreDependencies;
    readonly #view: NotificationCenterView;

    constructor(view: NotificationCenterView, loadMoreDependencies: NotificationCenterLoadMoreDependencies) {
        this.#view = view;
        this.#loadMoreDependencies = loadMoreDependencies;
    }

    syncSnapshot(request: NotificationCenterSnapshotRenderRequest): number {
        synchronizeExpandedNotificationIds(request.expandedNotificationIds, request.snapshot);
        const badgeCount = this.#view.updateBadge(request.elements, request.snapshot);
        this.render(request);
        return badgeCount;
    }

    render(request: NotificationCenterSnapshotRenderRequest): void {
        this.#view.render(request.elements, request.snapshot, {
            state: request.state,
            isLoadingMore: request.isLoadingMore,
            expandedNotificationIds: request.expandedNotificationIds
        });
        if (request.isVisible && request.isDropdownOpen) {
            this.syncExpandButtons(request.elements);
        }
    }

    syncExpandButtons(elements: NotificationCenterElements): void {
        this.#view.syncExpandButtons(elements);
    }

    requestLoadMoreIfNeeded(request: NotificationCenterLoadMoreRequest): void {
        if (!request.isVisible || !request.isExpanded || !request.isDropdownOpen || request.listElement === null) {
            return;
        }
        if (!this.#loadMoreDependencies.canLoadMore() || this.#loadMoreDependencies.isLoadingMore() || this.#loadMoreDependencies.isMarkingRead()) {
            return;
        }
        const distanceFromBottom = request.listElement.scrollHeight - request.listElement.scrollTop - request.listElement.clientHeight;
        if (distanceFromBottom > NOTIFICATION_SCROLL_LOAD_THRESHOLD_PX) {
            return;
        }
        this.#loadMoreDependencies.loadMore();
    }
}

export { NotificationCenterPresentationFlow };
export type { NotificationCenterSnapshotRenderRequest };

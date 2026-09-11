/* SoAI - Notifications feature notification center presentation flow [frontend/assets/ts/features/notifications/notificationCenterPresentationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationsListResponse } from '@core/notifications/types.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatTrackedTaskCounter } from '@core/tasks/taskCounterText.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { toggleHidden } from '@core/ui/visibility.ts';
import type { NotificationCenterSnapshotState } from '@features/notifications/NotificationCenterDataController.ts';
import { synchronizeExpandedNotificationIds } from '@features/notifications/notificationCenterExpandedState.ts';
import { NotificationCenterView } from '@features/notifications/NotificationCenterView.ts';
import type { NotificationCenterElements } from '@features/notifications/uiTypes.ts';

const NOTIFICATION_SCROLL_LOAD_THRESHOLD_PX = 64;
const TASK_ONLY_BADGE_CLASS = 'header-badge--background-activity';
const MIXED_BADGE_CLASS = 'header-badge--mixed-attention';

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

    syncSnapshot(request: NotificationCenterSnapshotRenderRequest): void {
        synchronizeExpandedNotificationIds(request.expandedNotificationIds, request.snapshot);
        this.render(request);
    }

    syncBadge(elements: NotificationCenterElements, unreadNotificationCount: number, backgroundOperationCount: number): number {
        const unreadCount = Math.max(0, unreadNotificationCount);
        const operationCount = Math.max(0, backgroundOperationCount);
        const displayedCount = unreadCount + operationCount;
        const hasUnreadNotifications = unreadCount > 0;
        const hasBackgroundOperations = operationCount > 0;
        const notificationText = hasUnreadNotifications ? i18n.t('header.notificationCenter.titleWithCount', { count: unreadCount }) : '';
        const operationText = hasBackgroundOperations ? formatTrackedTaskCounter(operationCount) : '';
        const attentionText = hasUnreadNotifications && hasBackgroundOperations ? `${notificationText} · ${operationText}` : notificationText || operationText || i18n.t('header.notificationCenter.title');
        dom.setText(elements.count, displayedCount > 0 ? String(displayedCount) : '');
        dom.toggleClass(elements.count, TASK_ONLY_BADGE_CLASS, !hasUnreadNotifications && hasBackgroundOperations);
        dom.toggleClass(elements.count, MIXED_BADGE_CLASS, hasUnreadNotifications && hasBackgroundOperations);
        toggleHidden(elements.count, displayedCount === 0);
        dom.setAttribute(elements.count, 'aria-label', attentionText);
        dom.setAttribute(elements.button, 'aria-label', attentionText);
        setTooltipText(elements.button, attentionText);
        return displayedCount;
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

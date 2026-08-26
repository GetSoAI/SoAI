/* SoAI - Notifications feature notification center read synchronizer [frontend/assets/ts/features/notifications/NotificationCenterReadSynchronizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { notificationRecordRequiresUserAttention } from '@core/notifications/classification.ts';
import type { NotificationsListResponse } from '@core/notifications/types.ts';
import type { NotificationCenterActions } from '@features/notifications/NotificationCenterActions.ts';
import type { NotificationCenterDataController } from '@features/notifications/NotificationCenterDataController.ts';

interface NotificationCenterReadSynchronizerDependencies {
    actions: NotificationCenterActions;
    dataController: NotificationCenterDataController;
    requestLoadMoreIfNeeded: () => void;
}

interface NotificationCenterReadSyncOptions {
    isExpanded: boolean;
    isVisible: boolean;
    snapshot: NotificationsListResponse | null;
}

class NotificationCenterReadSynchronizer {
    readonly #dependencies: NotificationCenterReadSynchronizerDependencies;
    #isMarkingRead = false;
    readonly #syncToken = new SequenceToken();

    constructor(dependencies: NotificationCenterReadSynchronizerDependencies) {
        this.#dependencies = dependencies;
    }

    isMarkingRead(): boolean {
        return this.#isMarkingRead;
    }

    destroy(): void {
        this.#syncToken.invalidate();
        this.#isMarkingRead = false;
    }

    syncLoadedNotifications(options: NotificationCenterReadSyncOptions): void {
        if (!options.isVisible || !options.isExpanded || this.#isMarkingRead || this.#dependencies.dataController.isLoadingMore()) {
            return;
        }
        const notificationIds = options.snapshot ? options.snapshot.notifications.filter((notification) => notification.readAtMs == null && !notificationRecordRequiresUserAttention(notification)).map((notification) => notification.id) : [];
        if (notificationIds.length === 0) {
            return;
        }
        this.#isMarkingRead = true;
        const syncGeneration = this.#syncToken.next();
        void this.#markLoadedNotificationsRead(notificationIds, syncGeneration)
            .then(() => {
                if (!this.#syncToken.isActive(syncGeneration)) {
                    return;
                }
                this.#isMarkingRead = false;
                this.#dependencies.requestLoadMoreIfNeeded();
            })
            .catch((error) => {
                if (!this.#syncToken.isActive(syncGeneration)) {
                    return;
                }
                this.#isMarkingRead = false;
                errorHandler.warn('NotificationCenter', 'Failed to mark notifications as read', ensureError(error));
            });
    }

    async #markLoadedNotificationsRead(notificationIds: string[], syncGeneration: number): Promise<void> {
        await this.#dependencies.actions.markNotificationsRead(notificationIds);
        if (!this.#syncToken.isActive(syncGeneration)) {
            return;
        }
        this.#dependencies.dataController.markLoadedNotificationsRead(notificationIds);
        await this.#dependencies.dataController.refreshHead(false);
    }
}

export { NotificationCenterReadSynchronizer };

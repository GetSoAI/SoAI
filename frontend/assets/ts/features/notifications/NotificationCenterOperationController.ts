/* SoAI - Notifications feature notification center operation controller [frontend/assets/ts/features/notifications/NotificationCenterOperationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import type { NotificationCenterActions } from '@features/notifications/NotificationCenterActions.ts';
import type { NotificationCenterDataController } from '@features/notifications/NotificationCenterDataController.ts';

interface NotificationCenterOperationControllerDependencies {
    actions: NotificationCenterActions;
    dataController: NotificationCenterDataController;
}

class NotificationCenterOperationController {
    readonly #dependencies: NotificationCenterOperationControllerDependencies;
    readonly #lifecycleToken = new SequenceToken();
    #pendingDeleteIds = new Set<string>();

    constructor(dependencies: NotificationCenterOperationControllerDependencies) {
        this.#dependencies = dependencies;
    }

    destroy(): void {
        this.#lifecycleToken.invalidate();
        this.#pendingDeleteIds.clear();
    }

    async clearAll(): Promise<void> {
        const operationGeneration = this.#lifecycleToken.value;
        try {
            const cleared = await this.#dependencies.actions.clearAll();
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            if (!cleared) {
                return;
            }
            await this.#dependencies.dataController.refreshHead(true);
            this.#pendingDeleteIds.clear();
        } catch (error) {
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            errorHandler.warn('NotificationCenter', 'Failed to clear notifications', ensureError(error));
            showNotification(i18n.t('common.errors.unknownError'), 'error');
        }
    }

    async deleteOne(notificationId: string): Promise<void> {
        const operationGeneration = this.#lifecycleToken.value;
        const normalizedNotificationId = notificationId.trim();
        if (!normalizedNotificationId || this.#pendingDeleteIds.has(normalizedNotificationId)) {
            return;
        }
        this.#pendingDeleteIds.add(normalizedNotificationId);
        try {
            const deleted = await this.#dependencies.actions.deleteOne(normalizedNotificationId);
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            if (!deleted) {
                return;
            }
            this.#dependencies.dataController.confirmNotificationDeleted(normalizedNotificationId);
            await this.#dependencies.dataController.refreshHead(false);
        } catch (error) {
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            errorHandler.warn('NotificationCenter', 'Failed to delete notification', ensureError(error));
            showNotification(i18n.t('common.errors.unknownError'), 'error');
        } finally {
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            this.#pendingDeleteIds.delete(normalizedNotificationId);
        }
    }

    async loadMore(): Promise<void> {
        const operationGeneration = this.#lifecycleToken.value;
        try {
            await this.#dependencies.dataController.loadMore();
        } catch (error) {
            if (!this.#lifecycleToken.isActive(operationGeneration)) {
                return;
            }
            errorHandler.warn('NotificationCenter', 'Failed to load older notifications', ensureError(error));
            showNotification(i18n.t('common.errors.unknownError'), 'error');
        }
    }
}

export { NotificationCenterOperationController };
export type { NotificationCenterOperationControllerDependencies };

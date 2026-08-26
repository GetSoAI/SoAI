/* SoAI - Notifications feature notification center attention opener [frontend/assets/ts/features/notifications/NotificationCenterAttentionOpener.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { NotificationRecord } from '@core/notifications/types.ts';
import type { NotificationCenterActions } from '@features/notifications/NotificationCenterActions.ts';
import type { NotificationCenterDataController } from '@features/notifications/NotificationCenterDataController.ts';
import { handleNotificationLink, openConversationAttentionNotificationLink } from '@features/notifications/notificationCenterListClickHandling.ts';

interface NotificationCenterAttentionOpenerDependencies {
    actions: NotificationCenterActions;
    dataController: NotificationCenterDataController;
    hide: () => void;
}

class NotificationCenterAttentionOpener {
    readonly #dependencies: NotificationCenterAttentionOpenerDependencies;

    constructor(dependencies: NotificationCenterAttentionOpenerDependencies) {
        this.#dependencies = dependencies;
    }

    async open(record: NotificationRecord): Promise<void> {
        try {
            const opened = await this.#dependencies.actions.openNotification(record.id);
            if (opened) {
                this.#dependencies.dataController.markLoadedNotificationsRead([record.id]);
            } else {
                await this.#dependencies.dataController.refreshHead(false);
                errorHandler.warn('NotificationCenter', 'Attention notification open did not confirm backend read state', ensureError(new Error('Notification open request failed')));
                return;
            }
            if (record.link) {
                if (record.link.linkType === 'conversation') {
                    await openConversationAttentionNotificationLink({
                        conversationId: record.link.value,
                        notificationId: record.id,
                        onHide: this.#dependencies.hide
                    });
                } else {
                    handleNotificationLink(record.link, this.#dependencies.hide);
                }
            }
            await this.#dependencies.dataController.refreshHead(false);
        } catch (error) {
            errorHandler.warn('NotificationCenter', 'Failed to open attention notification', ensureError(error));
        }
    }
}

export { NotificationCenterAttentionOpener };

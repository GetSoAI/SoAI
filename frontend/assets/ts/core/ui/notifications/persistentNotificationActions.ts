/* SoAI - Shared UI persistent notification actions [frontend/assets/ts/core/ui/notifications/persistentNotificationActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { NotificationButton } from '@core/ui/notifications/types.ts';

interface PersistentNotificationActionOptions {
    notification: HTMLElement;
    buttons: NotificationButton[];
    dismiss: () => void;
}

const setActionControlsPending = (notification: HTMLElement, pending: boolean): void => {
    const actions = dom.resolve('.ui-notification__actions', notification);
    if (actions) {
        dom.setAttribute(actions, 'aria-busy', pending ? 'true' : 'false');
    }
    for (const button of dom.resolveAll('.ui-notification__actions button', notification)) {
        if (button instanceof HTMLButtonElement) {
            button.disabled = pending;
        }
    }
};

const setActionFailureVisible = (notification: HTMLElement, visible: boolean): void => {
    const failure = dom.resolve('.ui-notification__action-error', notification);
    if (!(failure instanceof HTMLElement)) {
        throw new Error('Persistent notification action error element is required');
    }
    dom.setText(failure, visible ? i18n.t('common.notifications.actionFailed') : '');
    failure.hidden = !visible;
    dom.toggleClass(failure, 'u-hidden', !visible);
};

const bindPersistentNotificationActions = (options: PersistentNotificationActionOptions): void => {
    let actionPending = false;
    options.buttons.forEach((button, buttonIndex) => {
        const actionControl = dom.resolve(`[data-idx="${buttonIndex}"]`, options.notification);
        if (!(actionControl instanceof HTMLButtonElement)) {
            throw new Error(`Persistent notification action ${buttonIndex} is required`);
        }
        actionControl.addEventListener('click', () => {
            if (actionPending) {
                return;
            }
            terminateHandledPromise(
                (async (): Promise<void> => {
                    actionPending = true;
                    setActionFailureVisible(options.notification, false);
                    setActionControlsPending(options.notification, true);
                    try {
                        if (!button.action) {
                            options.dismiss();
                            return;
                        }
                        const result = await button.action();
                        if (result !== false) {
                            options.dismiss();
                        }
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        errorHandler.error('Notifications', 'Notification button action failed', runtimeError);
                        setActionFailureVisible(options.notification, true);
                    } finally {
                        actionPending = false;
                        setActionControlsPending(options.notification, false);
                    }
                })()
            );
        });
    });
};

export { bindPersistentNotificationActions };

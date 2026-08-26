/* SoAI - Notifications feature notification center DOM bindings [frontend/assets/ts/features/notifications/notificationCenterDomBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationRecord, NotificationsListResponse } from '@core/notifications/types.ts';
import type { EventHandler } from '@core/resourcetracker/types.ts';
import { handleNotificationCenterListClick } from '@features/notifications/notificationCenterListClickHandling.ts';
import type { NotificationCenterElements } from '@features/notifications/uiTypes.ts';

interface NotificationCenterDomBindingsLifecycle {
    addEventListener: (target: EventTarget, event: string, handler: EventHandler, options?: AddEventListenerOptions) => () => void;
}

interface BindNotificationCenterDomBindingsOptions {
    deleteNotification: (notificationId: string) => void;
    elements: NotificationCenterElements;
    expandOrCollapse: () => void;
    hide: () => void;
    lifecycle: NotificationCenterDomBindingsLifecycle;
    requestLoadMoreIfNeeded: () => void;
    toggle: () => void;
    openAttentionNotification: (record: NotificationRecord) => void;
    toggleExpandedNotification: (notificationId: string) => void;
    triggerClearAll: () => void;
    resolveSnapshot: () => NotificationsListResponse | null;
}

interface NotificationCenterLocalizationDom {
    getDocument: () => Document;
}

interface BindNotificationCenterLocalizationUpdatesOptions {
    dom: NotificationCenterLocalizationDom;
    lifecycle: NotificationCenterDomBindingsLifecycle;
    refreshRenderedLocalization: () => void;
}

const bindNotificationCenterDomBindings = (options: BindNotificationCenterDomBindingsOptions): void => {
    options.lifecycle.addEventListener(options.elements.button, 'click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        options.toggle();
    });
    options.lifecycle.addEventListener(options.elements.toggle, 'click', (event) => {
        event.stopPropagation();
        options.expandOrCollapse();
    });
    options.lifecycle.addEventListener(options.elements.toggle, 'keydown', (event) => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            options.expandOrCollapse();
        }
    });
    options.lifecycle.addEventListener(options.elements.clearAllButton, 'click', (event) => {
        event.stopPropagation();
        const snapshot = options.resolveSnapshot();
        if (!snapshot || snapshot.notifications.length === 0) {
            return;
        }
        options.triggerClearAll();
    });
    options.lifecycle.addEventListener(options.elements.list, 'scroll', () => options.requestLoadMoreIfNeeded());
    options.lifecycle.addEventListener(options.elements.list, 'click', (event) => {
        handleNotificationCenterListClick({
            listElement: options.elements.list,
            event,
            snapshot: options.resolveSnapshot(),
            onHide: () => options.hide(),
            onDelete: (notificationId) => options.deleteNotification(notificationId),
            onOpenAttention: (record) => options.openAttentionNotification(record),
            onToggleExpanded: (notificationId) => options.toggleExpandedNotification(notificationId)
        });
    });
};

const bindNotificationCenterLocalizationUpdates = (options: BindNotificationCenterLocalizationUpdatesOptions): void => {
    const doc = options.dom.getDocument();
    const win = doc.defaultView;
    if (!win) {
        throw new Error('NotificationCenter requires a Window');
    }
    options.lifecycle.addEventListener(win, 'soai:language:changed', options.refreshRenderedLocalization);
    options.lifecycle.addEventListener(win, 'soai:localization:changed', options.refreshRenderedLocalization);
};

export { bindNotificationCenterDomBindings, bindNotificationCenterLocalizationUpdates };

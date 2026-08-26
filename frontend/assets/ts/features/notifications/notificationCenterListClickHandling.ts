/* SoAI - Notifications feature notification center list click handling [frontend/assets/ts/features/notifications/notificationCenterListClickHandling.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { clearNotificationAttentionIntent, setNotificationAttentionIntent } from '@core/notifications/attentionIntent.ts';
import { notificationRecordRequiresUserAttention } from '@core/notifications/classification.ts';
import type { NotificationRecord, NotificationsListResponse } from '@core/notifications/types.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { securityApi } from '@core/security/public.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isNode } from '@core/typeGuards.ts';

const isInternalNotificationRoute = (value: string): boolean => {
    const sanitized = securityApi.sanitizeUrl(value, { allowRelative: true, allowBlob: false, allowDataImage: false });
    if (!sanitized) {
        return false;
    }
    return !securityApi.isAbsoluteHttpUrl(sanitized);
};

const handleNotificationLink = (link: { linkType: string; value: string }, onHide: () => void): void => {
    onHide();
    if (link.linkType === 'conversation') {
        const targetRoute = `chat/conversation/${encodeSegment(link.value)}`;
        try {
            const router = requireRouter();
            void router.navigate(targetRoute, { pushState: true }).catch((error) => {
                errorHandler.warn('NotificationCenter', 'Failed to navigate to notification conversation', ensureError(error));
            });
        } catch (error) {
            errorHandler.warn('NotificationCenter', 'Failed to resolve router for notification navigation', ensureError(error));
        }
        return;
    }
    if (link.linkType === 'automation_run') {
        try {
            const router = requireRouter();
            void router.navigate('automation', { pushState: true, query: { 'run_id': link.value } }).catch((error) => {
                errorHandler.warn('NotificationCenter', 'Failed to navigate to automation from notification', ensureError(error));
            });
        } catch (error) {
            errorHandler.warn('NotificationCenter', 'Failed to resolve router for notification navigation', ensureError(error));
        }
        return;
    }
    if (link.linkType === 'url') {
        if (isInternalNotificationRoute(link.value)) {
            try {
                const router = requireRouter();
                void router.navigate(link.value, { pushState: true }).catch((error) => {
                    errorHandler.warn('NotificationCenter', 'Failed to navigate to internal notification route', ensureError(error));
                });
            } catch (error) {
                errorHandler.warn('NotificationCenter', 'Failed to resolve router for internal notification route', ensureError(error));
            }
            return;
        }
        void requireDialogsService()
            .showExternalLinkModal({ url: link.value })
            .catch((error) => {
                errorHandler.warn('NotificationCenter', 'Failed to open external link for notification', ensureError(error));
            });
    }
};

const openConversationAttentionNotificationLink = async (inputArguments: { conversationId: string; notificationId: string; onHide: () => void }): Promise<boolean> => {
    const conversationId = inputArguments.conversationId.trim();
    const notificationId = inputArguments.notificationId.trim();
    if (!conversationId || !notificationId) {
        throw new Error('Attention notification navigation requires conversation and notification ids');
    }
    const targetRoute = `chat/conversation/${encodeSegment(conversationId)}`;
    const router = requireRouter();
    setNotificationAttentionIntent({ conversationId, notificationId });
    inputArguments.onHide();
    try {
        await router.navigate(targetRoute, { pushState: true });
        return true;
    } catch (error) {
        clearNotificationAttentionIntent({ conversationId, notificationId });
        errorHandler.warn('NotificationCenter', 'Failed to navigate to attention notification conversation', ensureError(error));
        return false;
    }
};

const handleNotificationEntryClick = (entryElement: HTMLElement, snapshot: NotificationsListResponse | null, event: Event, onHide: () => void, onOpenAttention: (record: NotificationRecord) => void, onToggleExpanded: (notificationId: string) => void): void => {
    const notificationId = entryElement.dataset['notificationId']?.trim() ?? '';
    if (!notificationId) {
        throw new Error('Notification item click missing notification id');
    }
    const record = snapshot ? snapshot.notifications.find((candidate) => candidate.id === notificationId) : null;
    if (!record) {
        return;
    }
    if (!notificationRecordRequiresUserAttention(record)) {
        if (record.link) {
            event.preventDefault();
            event.stopPropagation();
            handleNotificationLink(record.link, onHide);
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const isExpanded = entryElement.classList.contains('notification-item--expanded');
        const messageElement = dom.resolve('.notification-item-message-content', entryElement);
        const hasOverflow = messageElement instanceof HTMLElement && messageElement.scrollHeight > messageElement.clientHeight;
        if (isExpanded || hasOverflow) {
            onToggleExpanded(notificationId);
        }
        return;
    }
    const link = record ? record.link : null;
    if (!link) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    onOpenAttention(record);
};

const handleNotificationDeleteClick = (button: HTMLElement, event: Event, onDelete: (notificationId: string) => void): void => {
    event.stopPropagation();
    const notificationId = button.dataset['notificationId']?.trim() ?? '';
    if (!notificationId) {
        throw new Error('Notification delete button missing notification id');
    }
    onDelete(notificationId);
};

const handleNotificationExpandClick = (button: HTMLElement, event: Event, onToggleExpanded: (notificationId: string) => void): void => {
    event.preventDefault();
    event.stopPropagation();
    const notificationId = button.dataset['notificationId']?.trim() ?? '';
    if (!notificationId) {
        throw new Error('Notification expand button missing notification id');
    }
    onToggleExpanded(notificationId);
};

const handleNotificationCenterListClick = (inputArguments: { listElement: HTMLElement; event: Event; snapshot: NotificationsListResponse | null; onHide: () => void; onDelete: (notificationId: string) => void; onOpenAttention: (record: NotificationRecord) => void; onToggleExpanded: (notificationId: string) => void }): void => {
    const target = inputArguments.event.target;
    if (!isNode(target)) {
        throw new Error('NotificationCenter received click event with non-node target');
    }
    if (!(target instanceof Element)) {
        return;
    }
    if (!inputArguments.listElement.contains(target)) {
        return;
    }

    const deleteButton = target.closest('.notification-delete-btn');
    if (deleteButton instanceof HTMLElement) {
        handleNotificationDeleteClick(deleteButton, inputArguments.event, inputArguments.onDelete);
        return;
    }

    const expandButton = target.closest('.notification-expand-btn');
    if (expandButton instanceof HTMLElement) {
        handleNotificationExpandClick(expandButton, inputArguments.event, inputArguments.onToggleExpanded);
        return;
    }

    const entryElement = target.closest('.notification-item');
    if (!(entryElement instanceof HTMLElement)) {
        return;
    }
    handleNotificationEntryClick(entryElement, inputArguments.snapshot, inputArguments.event, inputArguments.onHide, inputArguments.onOpenAttention, inputArguments.onToggleExpanded);
};

export { handleNotificationCenterListClick, handleNotificationLink, openConversationAttentionNotificationLink };

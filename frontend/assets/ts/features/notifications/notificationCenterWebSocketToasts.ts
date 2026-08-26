/* SoAI - Notifications feature notification center WebSocket toasts [frontend/assets/ts/features/notifications/notificationCenterWebSocketToasts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiClient } from '@core/api/service.ts';
import { requireChatPagePresence } from '@core/chat/streamServiceAccess.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { i18n } from '@core/i18n/index.ts';
import { clearNotificationAttentionIntent, setNotificationAttentionIntent } from '@core/notifications/attentionIntent.ts';
import { notificationTextRequiresUserAttention } from '@core/notifications/classification.ts';
import type { NotificationCreatedToast } from '@core/notifications/toastParsing.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { getRouterOptional } from '@core/routing/router/routerRuntime.ts';
import { dismissPersistentNotificationsByDedupeKey, showNotification, showPersistentNotification } from '@core/ui/notifications/notifications.ts';

const isUserAttentionToastForActiveConversation = (toast: NotificationCreatedToast): boolean => {
    if (!notificationTextRequiresUserAttention(toast.titleText) && !notificationTextRequiresUserAttention(toast.messageText)) {
        return false;
    }
    if (!toast.link || toast.link.linkType !== 'conversation') {
        return false;
    }
    try {
        return requireChatPagePresence().isActivelyViewingConversation(toast.link.value);
    } catch (error) {
        errorHandler.warn('NotificationCenter', 'Failed to resolve chat presence for attention toast', ensureError(error));
        return false;
    }
};

const isUserAttentionToast = (toast: NotificationCreatedToast): boolean => {
    return notificationTextRequiresUserAttention(toast.titleText) || notificationTextRequiresUserAttention(toast.messageText);
};

const openAttentionToast = async (toast: NotificationCreatedToast): Promise<boolean> => {
    if (!toast.notificationId) {
        errorHandler.warn('NotificationCenter', 'Attention toast open requires a notification id', ensureError(new Error('Missing notification id')));
        return false;
    }
    try {
        await getApiClient().webui.notifications.open(toast.notificationId);
    } catch (error) {
        errorHandler.warn('NotificationCenter', 'Failed to mark attention notification opened from toast', ensureError(error));
        return false;
    }
    if (!toast.link || toast.link.linkType !== 'conversation') {
        return true;
    }
    const conversationId = toast.link.value;
    const notificationId = toast.notificationId;
    const router = getRouterOptional();
    if (!router) {
        errorHandler.warn('NotificationCenter', 'Failed to resolve router for attention toast', ensureError(new Error('Router unavailable')));
        return false;
    }
    setNotificationAttentionIntent({
        conversationId,
        notificationId
    });
    try {
        await router.navigate(`chat/conversation/${encodeSegment(conversationId)}`, { pushState: true });
        return true;
    } catch (error) {
        clearNotificationAttentionIntent({ conversationId, notificationId });
        errorHandler.warn('NotificationCenter', 'Failed to navigate to attention notification conversation', ensureError(error));
        return false;
    }
};

const bindNotificationCenterWebSocketToasts = (): (() => void) => {
    return subscribeManagedWebSocketContracts({
        label: 'NotificationCenter',
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.notification.created,
                invalidPayloadMessage: 'Notification created event payload is invalid',
                handler: (toast): void => {
                    if (isUserAttentionToastForActiveConversation(toast)) {
                        return;
                    }
                    if (isUserAttentionToast(toast) && toast.link?.linkType === 'conversation' && toast.notificationId) {
                        showPersistentNotification({
                            dedupeKey: toast.notificationId,
                            message: toast.resolvedMessage,
                            type: toast.type,
                            buttons: [
                                {
                                    text: i18n.t('header.notificationCenter.actions.open'),
                                    variant: 'warning',
                                    action: async (): Promise<boolean> => {
                                        return await openAttentionToast(toast);
                                    }
                                }
                            ]
                        });
                        return;
                    }
                    showNotification(toast.resolvedMessage, toast.type);
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.notification.markedRead,
                invalidPayloadMessage: 'Notifications marked-read event payload is invalid',
                handler: (event): void => {
                    dismissPersistentNotificationsByDedupeKey(event.notificationIds);
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.notification.deleted,
                invalidPayloadMessage: 'Notification deleted event payload is invalid',
                handler: (event): void => {
                    dismissPersistentNotificationsByDedupeKey(event.notificationIds);
                }
            })
        ]
    });
};

export { bindNotificationCenterWebSocketToasts };

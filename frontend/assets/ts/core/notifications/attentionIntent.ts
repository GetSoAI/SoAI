/* SoAI - Shared notifications attention intent [frontend/assets/ts/core/notifications/attentionIntent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type NotificationAttentionIntent = {
    conversationId: string;
    notificationId: string;
};

const activeIntents: Map<string, NotificationAttentionIntent> = new Map();

const buildIntentKey = (intent: NotificationAttentionIntent): string | null => {
    const conversationId = intent.conversationId.trim();
    const notificationId = intent.notificationId.trim();
    if (!conversationId || !notificationId) {
        return null;
    }
    return `${conversationId}\u0000${notificationId}`;
};

const setNotificationAttentionIntent = (intent: NotificationAttentionIntent): void => {
    const key = buildIntentKey(intent);
    if (!key) {
        return;
    }
    activeIntents.set(key, {
        conversationId: intent.conversationId.trim(),
        notificationId: intent.notificationId.trim()
    });
};

const clearNotificationAttentionIntent = (intent: NotificationAttentionIntent): void => {
    const key = buildIntentKey(intent);
    if (key) {
        activeIntents.delete(key);
    }
};

const consumeNotificationAttentionIntent = (intent: NotificationAttentionIntent): boolean => {
    const key = buildIntentKey(intent);
    if (!key || !activeIntents.has(key)) {
        return false;
    }
    activeIntents.delete(key);
    return true;
};

export { clearNotificationAttentionIntent, consumeNotificationAttentionIntent, setNotificationAttentionIntent };

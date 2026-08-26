/* SoAI - Shared UI notifications service [frontend/assets/ts/core/ui/notifications/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { hasFunctionProperty, isPlainObject } from '@core/typeGuards.ts';
import { isNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import type { NotificationPreferences, NotificationStoragePreferences, NotificationType } from '@core/ui/notifications/types.ts';
import { playSoundEffect } from '@core/ui/sound/engine.ts';
import type { SoundEffectName } from '@core/ui/sound/types.ts';

const { now } = Date;

let notificationContainer: HTMLElement | null = null;
let notificationPreferencesCache: NotificationPreferences | null = null;
const recentNotifications: Map<string, number> = new Map();

const isNotificationStoragePreferences = <T>(value: T): value is T & NotificationStoragePreferences => isPlainObject(value) && hasFunctionProperty(value, 'getNotificationDuration');

const requireNotificationPreferences = (): NotificationPreferences => {
    if (notificationPreferencesCache) {
        return notificationPreferencesCache;
    }
    const storageCandidate = requireStorageService();
    if (!isNotificationStoragePreferences(storageCandidate)) {
        throw new TypeError('Storage service must expose a getNotificationDuration() method');
    }

    notificationPreferencesCache = Object.freeze({
        getNotificationDuration: (): number => {
            const value = storageCandidate.getNotificationDuration();
            if (typeof value !== 'number' || !Number.isFinite(value)) {
                throw new TypeError('Storage service.getNotificationDuration() must return a finite number');
            }
            return value;
        }
    });
    return notificationPreferencesCache;
};

const resolveNotificationDurationMs = (duration: number | null): number => duration ?? requireNotificationPreferences().getNotificationDuration() * 1000;

const isNotificationDismissed = (notification: HTMLElement): boolean => dom.hasClass(notification, 'ui-notification--closing') || dom.hasClass(notification, 'ui-notification--swipe-dismissed');

const getNotificationContainer = (): HTMLElement => {
    if (!notificationContainer) {
        const existing = dom.resolve('#notification-container');
        const existingContainer = existing instanceof HTMLElement ? existing : null;
        const created = existingContainer || dom.create('div', { id: 'notification-container', className: 'ui-notification-stack' });
        if (!(created instanceof HTMLElement)) {
            throw new TypeError('Notification container must be an HTMLElement');
        }
        notificationContainer = created;
        const body = dom.getBody();
        if (!body) {
            throw new Error('Document body is unavailable');
        }
        if (!existingContainer) {
            dom.appendChild(body, notificationContainer);
        }
    }
    return notificationContainer;
};

const findRecentNotification = (message: string, type: NotificationType, container: HTMLElement): HTMLElement | null => {
    const key = `${type}:${message}`;
    const lastShown = recentNotifications.get(key);
    if (!lastShown || now() - lastShown >= 1000) {
        return null;
    }
    for (const node of dom.resolveAll('.ui-notification', container)) {
        if (!(node instanceof HTMLElement)) {
            continue;
        }
        if (isNotificationDismissed(node)) {
            continue;
        }
        const messageNode = dom.resolve('.ui-notification__message', node);
        if (messageNode?.textContent?.trim() === message) {
            return node;
        }
    }
    return null;
};

const rememberRecentNotification = (message: string, type: NotificationType): void => {
    const timestamp = now();
    const key = `${type}:${message}`;
    recentNotifications.set(key, timestamp);
    if (recentNotifications.size <= 50) {
        return;
    }
    const cutoff = timestamp - 1000;
    for (const [candidate, value] of recentNotifications.entries()) {
        if (value < cutoff) {
            recentNotifications.delete(candidate);
        }
    }
};

const resolveNotificationSoundEffect = (type: NotificationType): SoundEffectName => {
    if (type === 'warning') {
        return 'notificationWarning';
    }
    if (type === 'error' || type === 'danger') {
        return 'notificationDanger';
    }
    return 'notificationSuccess';
};

const playNotificationSound = (type: NotificationType = 'info'): void => {
    try {
        playSoundEffect(resolveNotificationSoundEffect(type));
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('Notifications', 'Playing notification sound failed', runtimeError);
    }
};

export { findRecentNotification, getNotificationContainer, isNotificationDismissed, isNotificationType, playNotificationSound, rememberRecentNotification, resolveNotificationDurationMs };

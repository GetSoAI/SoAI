/* SoAI - Shared UI notifications [frontend/assets/ts/core/ui/notifications/notifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { isArray, isPlainObject } from '@core/typeGuards.ts';
import { NOTIFICATION_DISMISS_FADE_MS, NOTIFICATION_ICON_MAP, USER_NOTIFICATION_DURATIONS } from '@core/ui/notifications/constants.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { createAutoDismissNotificationTimer } from '@core/ui/notifications/notificationTimer.ts';
import { bindPersistentNotificationActions } from '@core/ui/notifications/persistentNotificationActions.ts';
import { findRecentNotification, getNotificationContainer, isNotificationDismissed, isNotificationType, playNotificationSound, rememberRecentNotification, resolveNotificationDurationMs } from '@core/ui/notifications/service.ts';
import { bindToastNotificationInteractions, refreshToastNotificationInteractivity } from '@core/ui/notifications/toastNotificationInteractions.ts';
import type { NotificationButton, NotificationOptions, NotificationTimerControls, NotificationType, NotificationUserOptions } from '@core/ui/notifications/types.ts';
import { getIconFromStringSync } from '@core/ui/icons/iconservice/public.ts';

export type { NotificationType };

interface NotificationLifecycleController {
    dismiss: () => void;
    dismissWithFade: () => void;
    pauseAutoDismiss: () => void;
    resumeAutoDismiss: () => void;
    setTimerControls: (timerControls: NotificationTimerControls) => void;
}

const createNotificationLifecycleController = (options: { notification: HTMLElement; onRemove?: () => void }): NotificationLifecycleController => {
    let removed = false;
    let fading = false;
    let timerControls: NotificationTimerControls | null = null;

    const dismiss = (): void => {
        if (removed) {
            return;
        }
        removed = true;
        timerControls?.clear();
        dom.remove(options.notification);
        options.onRemove?.();
    };

    const dismissWithFade = (): void => {
        if (removed || fading) {
            return;
        }
        fading = true;
        timerControls?.clear();
        dom.addClass(options.notification, 'ui-notification--closing');
        window.setTimeout(dismiss, NOTIFICATION_DISMISS_FADE_MS);
    };

    return {
        dismiss,
        dismissWithFade,
        pauseAutoDismiss: (): void => timerControls?.pause(),
        resumeAutoDismiss: (): void => timerControls?.resume(),
        setTimerControls: (nextTimerControls: NotificationTimerControls): void => {
            timerControls = nextTimerControls;
        }
    };
};

const showNotification = (message: string, type: NotificationType = 'info', duration: number | null = null): HTMLElement => {
    const effectiveDuration = resolveNotificationDurationMs(duration);
    const normalizedMessage = toTrimmedString(message);
    const container = getNotificationContainer();

    const existing = findRecentNotification(normalizedMessage, type, container);
    if (existing) {
        return existing;
    }
    rememberRecentNotification(normalizedMessage, type);

    const notification = dom.create('div', { className: `ui-notification ui-notification--${type}` });
    if (!(notification instanceof HTMLElement)) {
        throw new TypeError('Notification element must be an HTMLElement');
    }

    const icon = NOTIFICATION_ICON_MAP[type];
    const closeLabel = i18n.t('common.close');
    const closeIcon = getIconFromStringSync('close', { size: 14, strokeWidth: 1.5 });
    dom.setHTML(notification, uiHtml`<div class="ui-notification__content"><div class="ui-notification__icon">${getIconFromStringSync(icon, { size: 16 })}</div><span class="ui-notification__message">${normalizedMessage}</span></div><button type="button" class="ui-notification__close ui-round-button" data-tooltip="${uiAttr(closeLabel)}" aria-label="${uiAttr(closeLabel)}">${closeIcon}</button>`, { escape: false });

    const lifecycle = createNotificationLifecycleController({ notification });
    const handleCloseClick = (): void => lifecycle.dismissWithFade();
    dom.resolve('.ui-notification__close', notification)?.addEventListener('click', handleCloseClick);
    bindToastNotificationInteractions({ notification, lifecycle, copyNotificationMessage });
    dom.appendChild(container, notification);
    dom.flush();
    refreshToastNotificationInteractivity(notification);
    playNotificationSound(type);

    if (effectiveDuration > 0) {
        const timerControls = createAutoDismissNotificationTimer({
            durationMs: effectiveDuration,
            dismiss: lifecycle.dismissWithFade
        });
        lifecycle.setTimerControls(timerControls);
    }

    return notification;
};

const showPersistentNotification = (options: NotificationOptions | string, type?: NotificationType, buttons?: NotificationButton[]): HTMLElement | null => {
    const config: NotificationOptions = isPlainObject(options) ? { ...options } : typeof options === 'string' ? { message: options, type: type ?? 'info', buttons: buttons ?? [] } : { message: '', type: type ?? 'info', buttons: buttons ?? [] };

    if (!config.message) {
        return null;
    }

    const candidateType = config.type ?? null;
    const resolvedType: NotificationType = isNotificationType(candidateType) ? candidateType : 'info';
    const container = getNotificationContainer();
    const normalizedMessage = toTrimmedString(config.message);
    const dedupeKey = toTrimmedString(config.dedupeKey);

    if (normalizedMessage) {
        for (const node of dom.resolveAll('.ui-notification--persistent', container)) {
            if (!(node instanceof HTMLElement)) {
                continue;
            }
            if (isNotificationDismissed(node)) {
                continue;
            }
            if (dedupeKey && node.dataset['notificationDedupeKey'] === dedupeKey) {
                return node;
            }
            if (dedupeKey) {
                continue;
            }
            const messageNode = dom.resolve('.ui-notification__message', node);
            if (messageNode?.textContent?.trim() === normalizedMessage) {
                return node;
            }
        }
    }

    if (!isArray(config.buttons)) {
        throw new TypeError('Notification buttons must be an array');
    }
    config.buttons = config.buttons.slice(0, 2);

    const notification = dom.create('div', {
        className: `ui-notification ui-notification--persistent ui-notification--${resolvedType}`
    });
    if (!(notification instanceof HTMLElement)) {
        throw new TypeError('Persistent notification must be an HTMLElement');
    }
    if (dedupeKey) {
        notification.dataset['notificationDedupeKey'] = dedupeKey;
    }

    const iconMarkup = getIconFromStringSync(config.icon || resolvedType, { size: 18 });
    const buttonMarkup = config.buttons.map((button, index) => {
        const icon = button.icon ? getIconFromStringSync(button.icon, { size: 14 }) : EMPTY_UI_HTML;
        const hasIcon = Boolean(icon.html.trim());
        const variantClass = button.variant ? `ui-variant-${button.variant}` : index === 0 ? 'ui-variant-accent' : '';
        const gap = hasIcon ? '\u00A0' : '';
        return uiHtml`<button type="button" class="ui-button ${variantClass}" data-idx="${uiAttr(index)}" aria-label="${uiAttr(button.text)}" data-tooltip="${uiAttr(button.text)}">${icon}${gap}${button.text}</button>`;
    });
    const actionsMarkup = buttonMarkup.length ? uiHtml`<div class="ui-notification__actions">${toTrustedUiHtml(buttonMarkup.map((entry) => entry.html).join(''))}</div>` : EMPTY_UI_HTML;

    const closeLabel = i18n.t('common.close');
    const closeIcon = getIconFromStringSync('close', { size: 14, strokeWidth: 1.5 });
    dom.setHTML(notification, uiHtml`<div class="ui-notification__content"><div class="ui-notification__body"><div class="ui-notification__icon">${iconMarkup}</div><span class="ui-notification__message">${config.message}</span></div>${actionsMarkup}<div class="ui-notification__action-error u-hidden" role="alert" hidden></div></div><button type="button" class="ui-notification__close ui-round-button" data-tooltip="${uiAttr(closeLabel)}" aria-label="${uiAttr(closeLabel)}">${closeIcon}</button>`, { escape: false });

    const lifecycle = createNotificationLifecycleController({
        notification,
        onRemove: (): void => {
            try {
                config.onClose?.();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.error('Notifications', 'Persistent notification onClose failed', runtimeError);
            }
        }
    });

    dom.resolve('.ui-notification__close', notification)?.addEventListener('click', lifecycle.dismissWithFade);
    bindToastNotificationInteractions({ notification, lifecycle, copyNotificationMessage });
    bindPersistentNotificationActions({
        notification,
        buttons: config.buttons,
        dismiss: lifecycle.dismissWithFade
    });

    dom.appendChild(container, notification);
    dom.flush();
    refreshToastNotificationInteractivity(notification);
    playNotificationSound(resolvedType);
    return notification;
};

const dismissNotificationWithFade = (notification: HTMLElement): boolean => {
    if (isNotificationDismissed(notification)) {
        return false;
    }
    dom.addClass(notification, 'ui-notification--closing');
    window.setTimeout(() => {
        dom.remove(notification);
        dom.flush();
    }, NOTIFICATION_DISMISS_FADE_MS);
    return true;
};

const dismissPersistentNotifications = (messages: string | string[]): number => {
    const entries = isArray(messages) ? messages : [messages];
    const normalizedMessages = entries.map((entry) => toTrimmedString(entry)).filter(Boolean);
    if (!normalizedMessages.length) {
        return 0;
    }

    const container = getNotificationContainer();
    const nodes: HTMLElement[] = [];
    for (const node of dom.resolveAll('.ui-notification--persistent', container)) {
        if (node instanceof HTMLElement) {
            nodes.push(node);
        }
    }

    let removed = 0;
    nodes.forEach((node) => {
        const message = dom.resolve('.ui-notification__message', node)?.textContent?.trim() || '';
        if (normalizedMessages.includes(message) && dismissNotificationWithFade(node)) {
            removed += 1;
        }
    });

    if (removed > 0) {
        dom.flush();
    }
    return removed;
};

const dismissPersistentNotificationsByDedupeKey = (dedupeKeys: string | string[]): number => {
    const entries = isArray(dedupeKeys) ? dedupeKeys : [dedupeKeys];
    const normalizedKeys = entries.map((entry) => toTrimmedString(entry)).filter(Boolean);
    if (!normalizedKeys.length) {
        return 0;
    }
    const container = getNotificationContainer();
    let removed = 0;
    for (const node of dom.resolveAll('.ui-notification--persistent', container)) {
        if (!(node instanceof HTMLElement)) {
            continue;
        }
        const dedupeKey = node.dataset['notificationDedupeKey']?.trim() ?? '';
        if (!normalizedKeys.includes(dedupeKey)) {
            continue;
        }
        if (dismissNotificationWithFade(node)) {
            removed += 1;
        }
    }
    if (removed > 0) {
        dom.flush();
    }
    return removed;
};

const showUserNotification = (type: NotificationType, message: string, options: NotificationUserOptions = {}): void => {
    if (options.showNotification ?? true) {
        showNotification(message, type, options.duration ?? USER_NOTIFICATION_DURATIONS[type]);
    }
};

const copyNotificationMessage = async (message: string): Promise<void> => {
    await copyTextWithBrowserClipboardFeedback(
        {
            showNotification: (notificationMessage, type, duration): void => {
                showNotification(notificationMessage, type, duration);
            }
        },
        {
            text: message,
            successMessage: i18n.t('common.clipboard.copied'),
            errorMessage: i18n.t('common.clipboard.copyFailed'),
            unavailableMessage: i18n.t('common.clipboard.copyUnavailable')
        }
    );
};

const showUserError = (message: string, options: NotificationUserOptions = {}): void => {
    showUserNotification('error', message, options);
};

const showUserWarning = (message: string, options: NotificationUserOptions = {}): void => {
    showUserNotification('warning', message, options);
};

const showUserSuccess = (message: string, options: NotificationUserOptions = {}): void => {
    showUserNotification('success', message, options);
};

export { dismissPersistentNotifications, dismissPersistentNotificationsByDedupeKey, showNotification, showPersistentNotification, showUserError, showUserSuccess, showUserWarning };

/* SoAI - Shared UI toast notification interactions [frontend/assets/ts/core/ui/notifications/toastNotificationInteractions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { closest, dom } from '@core/dom/dom.ts';
import { bindToastNotificationSwipeDismissal } from '@core/ui/notifications/toastNotificationSwipe.ts';
import type { NotificationInteractionLifecycle } from '@core/ui/notifications/types.ts';

const NOTIFICATION_CLICK_SUPPRESSION_MS = 350;
const NOTIFICATION_EXPANSION_MEASUREMENT_TOLERANCE_PX = 1;

interface ToastNotificationInteractionOptions {
    notification: HTMLElement;
    lifecycle: NotificationInteractionLifecycle;
}

const isNotificationControlTarget = (target: EventTarget | null): boolean => {
    if (!(target instanceof Element)) {
        return false;
    }
    return closest(target, '.ui-notification__close, .ui-notification__actions, button, a, input, select, textarea') !== null;
};

const isNotificationSwipeBlockedTarget = (target: EventTarget | null): boolean => {
    if (!(target instanceof Element)) {
        return false;
    }
    return closest(target, '.ui-notification__close, .ui-notification__actions, button, a, input, select, textarea') !== null;
};

const resolveMessageElement = (notification: HTMLElement): HTMLElement | null => {
    const message = dom.resolve('.ui-notification__message', notification);
    return message instanceof HTMLElement ? message : null;
};

const hasHiddenMessageContent = (notification: HTMLElement): boolean => {
    const message = resolveMessageElement(notification);
    if (!message) {
        return false;
    }
    const wasExpanded = dom.hasClass(notification, 'ui-notification--expanded');
    if (wasExpanded) {
        dom.removeClass(notification, 'ui-notification--expanded');
    }
    const hasHiddenContent = message.scrollHeight > message.clientHeight + NOTIFICATION_EXPANSION_MEASUREMENT_TOLERANCE_PX || message.scrollWidth > message.clientWidth + NOTIFICATION_EXPANSION_MEASUREMENT_TOLERANCE_PX;
    if (wasExpanded) {
        dom.addClass(notification, 'ui-notification--expanded');
    }
    return hasHiddenContent;
};

const selectionBelongsToNotification = (notification: HTMLElement, selection: Selection): boolean => {
    if (selection.rangeCount <= 0) {
        return false;
    }
    const range = selection.getRangeAt(0);
    const commonAncestor = range.commonAncestorContainer;
    if (commonAncestor instanceof Element) {
        return notification.contains(commonAncestor);
    }
    const parentElement = commonAncestor.parentElement;
    return parentElement instanceof HTMLElement && notification.contains(parentElement);
};

const hasActiveNotificationTextSelection = (notification: HTMLElement): boolean => {
    const selection = window.getSelection();
    return Boolean(selection && selection.toString().trim().length > 0 && selectionBelongsToNotification(notification, selection));
};

const refreshToastNotificationInteractivity = (notification: HTMLElement): void => {
    const expandable = hasHiddenMessageContent(notification);
    dom.toggleClass(notification, 'ui-notification--expandable', expandable);
    if (!expandable && dom.hasClass(notification, 'ui-notification--expanded')) {
        dom.removeClass(notification, 'ui-notification--expanded');
        dom.setAttribute(notification, 'aria-expanded', 'false');
    }
};

const bindToastNotificationInteractions = (options: ToastNotificationInteractionOptions): void => {
    const { notification, lifecycle } = options;
    let suppressNextClick = false;
    let suppressNextClickTimer: ReturnType<typeof setTimeout> | null = null;

    const isExpanded = (): boolean => dom.hasClass(notification, 'ui-notification--expanded');
    const isExpandable = (): boolean => dom.hasClass(notification, 'ui-notification--expandable');

    const clearClickSuppression = (): void => {
        suppressNextClick = false;
        if (suppressNextClickTimer) {
            clearTimeout(suppressNextClickTimer);
            suppressNextClickTimer = null;
        }
    };

    const suppressUpcomingClick = (): void => {
        clearClickSuppression();
        suppressNextClick = true;
        suppressNextClickTimer = setTimeout(clearClickSuppression, NOTIFICATION_CLICK_SUPPRESSION_MS);
    };

    const toggleExpanded = (): void => {
        refreshToastNotificationInteractivity(notification);
        if (!isExpandable()) {
            return;
        }
        const nextExpanded = !isExpanded();
        dom.toggleClass(notification, 'ui-notification--expanded', nextExpanded);
        dom.setAttribute(notification, 'aria-expanded', nextExpanded ? 'true' : 'false');
        if (nextExpanded) {
            lifecycle.pauseAutoDismiss();
            return;
        }
        lifecycle.resumeAutoDismiss();
    };

    const handleMouseEnter = (): void => {
        lifecycle.pauseAutoDismiss();
    };

    const handleMouseLeave = (): void => {
        if (!isExpanded()) {
            lifecycle.resumeAutoDismiss();
        }
    };

    const handleClick = (event: MouseEvent): void => {
        if (suppressNextClick) {
            clearClickSuppression();
            event.preventDefault();
            event.stopPropagation();
            return;
        }
        if (isNotificationControlTarget(event.target)) {
            return;
        }
        if (hasActiveNotificationTextSelection(notification)) {
            return;
        }
        toggleExpanded();
    };

    dom.setAttribute(notification, 'aria-expanded', 'false');
    notification.addEventListener('click', handleClick);
    notification.addEventListener('mouseenter', handleMouseEnter);
    notification.addEventListener('mouseleave', handleMouseLeave);
    bindToastNotificationSwipeDismissal({
        notification,
        lifecycle,
        isExpanded,
        isBlockedTarget: isNotificationSwipeBlockedTarget,
        suppressUpcomingClick
    });
};

export { bindToastNotificationInteractions, refreshToastNotificationInteractivity };

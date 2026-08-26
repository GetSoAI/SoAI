/* SoAI - Notifications feature notification center expanded DOM [frontend/assets/ts/features/notifications/notificationCenterExpandedDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { toggleNotificationExpandedId } from '@features/notifications/notificationCenterExpandedState.ts';

const applyExpandedContentStyles = (contentElement: HTMLElement): void => {
    contentElement.style.setProperty('display', 'block');
    contentElement.style.setProperty('-webkit-line-clamp', 'unset');
    contentElement.style.setProperty('white-space', 'normal');
    contentElement.style.setProperty('overflow', 'visible');
    contentElement.style.setProperty('text-overflow', 'clip');
};

const removeExpandedContentStyles = (contentElement: HTMLElement): void => {
    contentElement.style.removeProperty('display');
    contentElement.style.removeProperty('-webkit-line-clamp');
    contentElement.style.removeProperty('white-space');
    contentElement.style.removeProperty('overflow');
    contentElement.style.removeProperty('text-overflow');
};

const toggleExpandedNotificationItem = (options: { listElement: HTMLElement; expandedNotificationIds: Set<string>; notificationId: string }): void => {
    const itemElement = dom.resolve(`[data-notification-id="${CSS.escape(options.notificationId)}"]`, options.listElement);
    if (!(itemElement instanceof HTMLElement)) {
        return;
    }
    const nowExpanded = toggleNotificationExpandedId(options.expandedNotificationIds, options.notificationId);
    const messageContent = dom.resolve('.notification-item-message-content', itemElement);
    const messageWrapper = dom.resolve('.notification-item-message', itemElement);
    if (nowExpanded) {
        itemElement.classList.add('notification-item--expanded');
        if (messageContent instanceof HTMLElement) {
            applyExpandedContentStyles(messageContent);
        }
        setTooltipText(itemElement, '');
        return;
    }
    itemElement.classList.remove('notification-item--expanded');
    const tooltipText = messageContent instanceof HTMLElement ? (messageContent.textContent?.trim() ?? '') : '';
    setTooltipText(itemElement, tooltipText);
    if (!(messageWrapper instanceof HTMLElement) || !(messageContent instanceof HTMLElement)) {
        return;
    }
    const onTransitionEnd = (event: Event): void => {
        if (!(event instanceof TransitionEvent) || event.propertyName !== 'max-height') {
            return;
        }
        messageWrapper.removeEventListener('transitionend', onTransitionEnd);
        removeExpandedContentStyles(messageContent);
    };
    messageWrapper.addEventListener('transitionend', onTransitionEnd);
};

export { toggleExpandedNotificationItem };

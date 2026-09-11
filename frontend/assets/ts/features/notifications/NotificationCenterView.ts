/* SoAI - Notifications feature notification center view [frontend/assets/ts/features/notifications/NotificationCenterView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { optionalTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { reconcileChildNodes, reconcileElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { dom } from '@core/dom/dom.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireHeaderDropdownButton, requireHeaderDropdownElement } from '@core/layout/header/dropdownElements.ts';
import { resolveNotificationText } from '@core/notifications/textResolution.ts';
import { resolveNotificationTimeLabel } from '@core/notifications/timeLabels.ts';
import type { NotificationsListResponse } from '@core/notifications/types.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { DROPDOWN_CHEVRON_OPTIONS } from '@core/ui/dropdown/chevron.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setIconSlot } from '@core/ui/icons/view.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { toggleHidden } from '@core/ui/visibility.ts';
import type { NotificationCenterSnapshotState } from '@features/notifications/NotificationCenterDataController.ts';
import type { NotificationCenterElements } from '@features/notifications/uiTypes.ts';

const resolveNotificationRowKey = (child: HTMLElement): string | null => {
    if (!child.classList.contains('notification-item')) {
        return null;
    }
    return optionalTrimmedDataAttribute(child, 'notification-id') ?? null;
};

const createNotificationRowsParent = (target: HTMLElement, html: TrustedHtml): HTMLElement => {
    const parent = target.ownerDocument.createElement('div');
    const fragment = createHtmlFragment({ documentRef: target.ownerDocument, html: html.html, context: target });
    parent.appendChild(fragment);
    return parent;
};

const insertNotificationRow = (parent: HTMLElement, child: HTMLElement, anchor: ChildNode | null): HTMLElement => {
    parent.insertBefore(child, anchor);
    return child;
};

const patchNotificationRow = (existingChild: HTMLElement, createdChild: HTMLElement): boolean => {
    if (existingChild.outerHTML === createdChild.outerHTML) {
        return false;
    }
    syncElementShell({ target: existingChild, source: createdChild });
    reconcileChildNodes(existingChild, Array.from(createdChild.childNodes));
    return true;
};

const removeNotificationRow = (child: HTMLElement): void => {
    child.remove();
};

const replaceUnsupportedNotificationRows = (target: HTMLElement, createdParent: HTMLElement): boolean => {
    target.replaceChildren(...Array.from(createdParent.children));
    return true;
};

const reconcileNotificationRows = (target: HTMLElement, html: TrustedHtml): void => {
    const createdParent = createNotificationRowsParent(target, html);
    patchOrderedChildren({
        existingParent: target,
        createdParent,
        resolveChildKey: resolveNotificationRowKey,
        insertChild: insertNotificationRow,
        patchChild: patchNotificationRow,
        removeChild: removeNotificationRow,
        replaceUnsupportedChildren(): boolean {
            return replaceUnsupportedNotificationRows(target, createdParent);
        }
    });
};

const isNotificationMessageExpandable = (itemElement: HTMLElement): boolean => {
    const messageContent = dom.resolve('.notification-item-message-content', itemElement);
    if (!(messageContent instanceof HTMLElement)) {
        return false;
    }
    const isExpanded = itemElement.classList.contains('notification-item--expanded');
    if (isExpanded) {
        return true;
    }
    return messageContent.scrollHeight > messageContent.clientHeight;
};

const syncNotificationExpandButtons = (listElement: HTMLElement): void => {
    const itemElements = dom.resolveAll('.notification-item', listElement);
    itemElements.forEach((itemElement) => {
        if (!(itemElement instanceof HTMLElement)) {
            return;
        }
        const expandButton = dom.resolve('.notification-expand-btn', itemElement);
        if (!(expandButton instanceof HTMLButtonElement)) {
            return;
        }
        const isExpandable = isNotificationMessageExpandable(itemElement);
        toggleHidden(expandButton, !isExpandable);
        expandButton.toggleAttribute('disabled', !isExpandable);
        dom.setAttribute(expandButton, 'aria-hidden', isExpandable ? 'false' : 'true');
    });
};

class NotificationCenterView {
    #closeIconMarkup: ReturnType<typeof getIconSync> | null = null;
    #expandIconMarkup: ReturnType<typeof getIconSync> | null = null;
    #chevronMarkup: ReturnType<typeof getIconSync> | null = null;

    resolveElements(): NotificationCenterElements {
        const manager = requireHeaderDropdownElement('#header-notification-manager', 'notification list manager');
        return {
            wrapper: requireHeaderDropdownElement('.notification-wrapper', 'notification wrapper'),
            button: requireHeaderDropdownElement('#notification-button', 'notification toggle button'),
            count: requireHeaderDropdownElement('#notification-count', 'notification count display'),
            center: requireHeaderDropdownElement('#header-notification-center', 'notification center container'),
            manager,
            toggle: requireHeaderDropdownElement('.header-notification-manager-toggle', 'notification list toggle'),
            panel: requireHeaderDropdownElement('#header-notification-list-panel', 'notification list panel'),
            chevron: requireHeaderDropdownElement('.notifications-chevron', 'notification list chevron icon', manager),
            title: requireHeaderDropdownElement('#header-notification-title', 'notification title'),
            list: requireHeaderDropdownElement('#notification-list', 'notification list'),
            clearAllButton: requireHeaderDropdownButton('#clear-all-notifications', 'clear-all'),
            loadingFooter: requireHeaderDropdownElement('#notification-loading-footer', 'loading footer')
        };
    }

    applyAria(elements: NotificationCenterElements, isVisible: boolean): void {
        dom.setAttribute(elements.button, 'aria-haspopup', 'true');
        dom.setAttribute(elements.button, 'aria-expanded', isVisible ? 'true' : 'false');
        dom.setAttribute(elements.center, 'aria-label', i18n.t('header.notificationCenter.aria.panel'));
    }

    applyLocalization(elements: NotificationCenterElements, isExpanded: boolean): void {
        const toggleLabel = i18n.t('header.notificationCenter.title');
        dom.setAttribute(elements.toggle, 'role', 'button');
        dom.setAttribute(elements.toggle, 'tabindex', '0');
        dom.setAttribute(elements.toggle, 'aria-controls', elements.panel.id);
        dom.setAttribute(elements.toggle, 'aria-label', toggleLabel);
        setTooltipText(elements.toggle, toggleLabel);
        this.setExpandedState(elements, isExpanded);
        this.setupIcons(elements);
    }

    setExpandedState(elements: NotificationCenterElements, isExpanded: boolean): void {
        dom.setAttribute(elements.toggle, 'aria-expanded', isExpanded ? 'true' : 'false');
        dom.toggleClass(elements.manager, 'header-notification-manager--expanded', isExpanded);
        dom.setAttribute(elements.panel, 'aria-hidden', isExpanded ? 'false' : 'true');
    }

    setupIcons(elements: NotificationCenterElements): void {
        const iconMarkup = this.#getChevronIconMarkup();
        setIconSlot(elements.chevron, iconMarkup, { className: elements.chevron.className });
    }

    render(elements: NotificationCenterElements, snapshot: NotificationsListResponse | null, options: { state: NotificationCenterSnapshotState; isLoadingMore: boolean; expandedNotificationIds: ReadonlySet<string> }): void {
        const notifications = snapshot ? snapshot.notifications : [];
        toggleHidden(elements.clearAllButton, notifications.length === 0);
        if (snapshot && snapshot.totalCount > 0) {
            dom.setText(elements.title, i18n.t('header.notificationCenter.titleWithCount', { count: snapshot.totalCount }));
        } else {
            dom.setText(elements.title, i18n.t('header.notificationCenter.title'));
        }

        elements.clearAllButton.toggleAttribute('disabled', notifications.length === 0);
        const clearAllLabel = i18n.t('header.notificationCenter.actions.clearAll');
        dom.setHTML(elements.clearAllButton, this.#getCloseIconMarkup(), { escape: false });
        setTooltipText(elements.clearAllButton, clearAllLabel);
        dom.setAttribute(elements.clearAllButton, 'aria-label', clearAllLabel);
        const isLoadingFooterVisible = notifications.length > 0 && options.isLoadingMore;
        toggleHidden(elements.loadingFooter, !isLoadingFooterVisible);
        dom.setAttribute(elements.loadingFooter, 'aria-hidden', isLoadingFooterVisible ? 'false' : 'true');
        const loadingText = dom.resolve('.header-dropdown-loading-text', elements.loadingFooter);
        if (loadingText instanceof HTMLElement) {
            dom.setText(loadingText, i18n.t('header.notificationCenter.actions.loadingMore'));
        }

        if (notifications.length === 0) {
            const message = options.state.status === 'unavailable' ? i18n.t('header.notificationCenter.messages.unavailable') : i18n.t('header.notificationCenter.messages.noNotifications');
            const emptyMarkup = uiHtml`<div class="task-list-empty notification-list-empty"><p>${message}</p></div>`;
            reconcileElementChildrenFromTrustedHtml({ target: elements.list, html: emptyMarkup });
            return;
        }

        const deleteLabel = i18n.t('header.notificationCenter.actions.delete');
        const deleteIcon = this.#getCloseIconMarkup();
        const expandLabel = i18n.t('header.notificationCenter.actions.expand');
        const expandIcon = this.#getExpandIconMarkup();

        const entries = notifications.map((notification, index) => {
            const unread = notification.readAtMs == null;
            const isExpanded = options.expandedNotificationIds.has(notification.id);
            const checkerboardClass = resolveCheckerboardClass(index);
            const classes = `dropdown-item notification-item ${checkerboardClass} ${unread ? 'notification-item--unread' : ''} notification-item--${notification.type} ${isExpanded ? 'notification-item--expanded' : ''}`;
            const createdLabel = resolveNotificationTimeLabel(notification.createdAtMs);
            const title = resolveNotificationText(notification.title);
            const message = resolveNotificationText(notification.message);
            const tooltipText = !isExpanded ? message : '';
            return uiHtml`<div class="${uiAttr(classes)}" data-notification-id="${uiAttr(notification.id)}" data-tooltip="${uiAttr(tooltipText)}"><div class="notification-item-body"><div class="notification-item-title-row"><span class="notification-item-title">${title}</span><span class="notification-item-time">${createdLabel}</span></div><div class="notification-item-message"><div class="notification-item-message-content">${message}</div></div></div><div class="notification-item-actions"><button class="ui-icon-button ui-icon-button--chromeless notification-delete-btn" type="button" data-notification-id="${uiAttr(notification.id)}" data-tooltip="${uiAttr(deleteLabel)}" aria-label="${uiAttr(deleteLabel)}">${deleteIcon}</button><button class="ui-icon-button ui-icon-button--chromeless notification-expand-btn u-hidden" type="button" data-notification-id="${uiAttr(notification.id)}" data-tooltip="${uiAttr(expandLabel)}" aria-label="${uiAttr(expandLabel)}" aria-hidden="true" disabled>${expandIcon}</button></div></div>`;
        });

        const listMarkup = toTrustedUiHtml(entries.map((entry) => entry.html).join(''));
        reconcileNotificationRows(elements.list, listMarkup);
    }

    syncExpandButtons(elements: NotificationCenterElements): void {
        syncNotificationExpandButtons(elements.list);
    }

    #getCloseIconMarkup(): ReturnType<typeof getIconSync> {
        if (this.#closeIconMarkup) {
            return this.#closeIconMarkup;
        }
        const markup = getIconSync('close', { size: 16, strokeWidth: 1.5 });
        this.#closeIconMarkup = markup;
        return markup;
    }

    #getExpandIconMarkup(): ReturnType<typeof getIconSync> {
        if (this.#expandIconMarkup) {
            return this.#expandIconMarkup;
        }
        const markup = getIconSync('chevron-down', DROPDOWN_CHEVRON_OPTIONS);
        this.#expandIconMarkup = markup;
        return markup;
    }

    #getChevronIconMarkup(): ReturnType<typeof getIconSync> {
        if (this.#chevronMarkup) {
            return this.#chevronMarkup;
        }
        const markup = getIconSync('chevron-down', DROPDOWN_CHEVRON_OPTIONS);
        this.#chevronMarkup = markup;
        return markup;
    }
}

export { NotificationCenterView };

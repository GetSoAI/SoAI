/* SoAI - Chat current conversation message window loading controller [frontend/assets/ts/pages/chat/controllers/page/renderer/currentConversationMessageWindowLoadingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { requireMessageWindowLoadingLabel } from '@pages/chat/dom.ts';

type MessageWindowLoadingDirection = 'before' | 'after';

type MessageWindowLoadingVisibility = {
    showEarlier: boolean;
    showNewer: boolean;
};

type MessageWindowLoadingInspection = {
    elements: HTMLElement[];
    before: HTMLElement | null;
    after: HTMLElement | null;
};

const MESSAGE_WINDOW_LOADING_CLASS = 'chat-message-window-loading';

const resolveLoadingLabel = (direction: MessageWindowLoadingDirection): string => {
    return direction === 'before' ? i18n.t('chat.conversation.loadingEarlierMessages') : i18n.t('chat.conversation.loadingNewerMessages');
};

const renderMessageWindowLoadingMarkup = (direction: MessageWindowLoadingDirection): TrustedHtml => {
    return uiHtml`<div class="${MESSAGE_WINDOW_LOADING_CLASS}" role="status" aria-live="polite"><span class="loading-spinner chat-message-window-loading-spinner" aria-hidden="true"></span><span class="chat-message-window-loading-label">${resolveLoadingLabel(direction)}</span></div>`;
};

const isMessageWindowLoadingElement = (element: Element): element is HTMLElement => {
    return element instanceof HTMLElement && element.classList.contains(MESSAGE_WINDOW_LOADING_CLASS);
};

const syncLoadingElementLabel = (element: HTMLElement, direction: MessageWindowLoadingDirection): boolean => {
    const label = requireMessageWindowLoadingLabel(element);
    const nextText = resolveLoadingLabel(direction);
    if (label.textContent === nextText) {
        return false;
    }
    label.textContent = nextText;
    return true;
};

const inspectMessageWindowLoadingElements = (container: Element, entries: readonly HTMLElement[]): MessageWindowLoadingInspection => {
    const firstEntry = entries[0] ?? null;
    const lastEntry = entries[entries.length - 1] ?? null;
    const elements: HTMLElement[] = [];
    let before: HTMLElement | null = null;
    let after: HTMLElement | null = null;
    let passedFirstEntry = firstEntry === null;
    let passedLastEntry = false;
    for (const child of container.children) {
        if (child === firstEntry) {
            passedFirstEntry = true;
        }
        if (child === lastEntry) {
            passedLastEntry = true;
            continue;
        }
        if (!isMessageWindowLoadingElement(child)) {
            continue;
        }
        elements.push(child);
        if (!passedFirstEntry && before === null) {
            before = child;
        }
        if (passedLastEntry && after === null) {
            after = child;
        }
    }
    return { elements, before, after };
};

const createMessageWindowLoadingElement = (container: Element, direction: MessageWindowLoadingDirection): HTMLElement => {
    const fragment = createHtmlFragment({
        documentRef: container.ownerDocument,
        html: renderMessageWindowLoadingMarkup(direction).html,
        context: container
    });
    const element = fragment.firstElementChild;
    if (!(element instanceof HTMLElement)) {
        throw new Error('Message window loading markup did not create an element');
    }
    return element;
};

const syncLoadingElementBeforeMessages = (container: Element, element: HTMLElement, firstEntry: HTMLElement): boolean => {
    if (element.parentElement !== container) {
        container.insertBefore(element, firstEntry);
        return true;
    }
    if (element.nextElementSibling !== firstEntry) {
        container.insertBefore(element, firstEntry);
        return true;
    }
    return false;
};

const syncLoadingElementAfterMessages = (container: Element, element: HTMLElement, lastEntry: HTMLElement): boolean => {
    if (element.parentElement !== container) {
        if (lastEntry.nextSibling === null) {
            container.append(element);
            return true;
        }
        container.insertBefore(element, lastEntry.nextSibling);
        return true;
    }
    if (lastEntry.nextElementSibling !== element) {
        container.insertBefore(element, lastEntry.nextSibling);
        return true;
    }
    return false;
};

const syncMessageWindowLoadingElement = (container: Element, direction: MessageWindowLoadingDirection, visible: boolean, existing: HTMLElement | null, firstEntry: HTMLElement, lastEntry: HTMLElement): boolean => {
    if (!visible) {
        if (existing === null) {
            return false;
        }
        existing.remove();
        return true;
    }
    const element = existing ?? createMessageWindowLoadingElement(container, direction);
    const labelUpdated = syncLoadingElementLabel(element, direction);
    const moved = direction === 'before' ? syncLoadingElementBeforeMessages(container, element, firstEntry) : syncLoadingElementAfterMessages(container, element, lastEntry);
    return existing === null || labelUpdated || moved;
};

const syncEmptyMessageWindowLoadingElements = (container: Element, visibility: MessageWindowLoadingVisibility, existing: readonly HTMLElement[]): boolean => {
    const desiredDirections: MessageWindowLoadingDirection[] = [];
    if (visibility.showEarlier) {
        desiredDirections.push('before');
    }
    if (visibility.showNewer) {
        desiredDirections.push('after');
    }
    let updated = false;
    for (let index = existing.length - 1; index >= desiredDirections.length; index -= 1) {
        const element = existing[index];
        if (element !== undefined) {
            element.remove();
            updated = true;
        }
    }
    for (let index = 0; index < desiredDirections.length; index += 1) {
        const direction = desiredDirections[index];
        if (direction === undefined) {
            continue;
        }
        const existingElement = existing[index] ?? null;
        const element = existingElement ?? createMessageWindowLoadingElement(container, direction);
        if (existingElement === null) {
            container.append(element);
            updated = true;
        }
        if (syncLoadingElementLabel(element, direction)) {
            updated = true;
        }
        if (container.children[index] !== element) {
            container.insertBefore(element, container.children[index] ?? null);
            updated = true;
        }
    }
    return updated;
};

const syncMessageWindowLoadingElements = (container: Element, visibility: MessageWindowLoadingVisibility, entries: readonly HTMLElement[]): boolean => {
    const inspection = inspectMessageWindowLoadingElements(container, entries);
    const firstEntry = entries[0] ?? null;
    const lastEntry = entries[entries.length - 1] ?? null;
    if (firstEntry === null || lastEntry === null) {
        return syncEmptyMessageWindowLoadingElements(container, visibility, inspection.elements);
    }
    const earlierUpdated = syncMessageWindowLoadingElement(container, 'before', visibility.showEarlier, inspection.before, firstEntry, lastEntry);
    const newerUpdated = syncMessageWindowLoadingElement(container, 'after', visibility.showNewer, inspection.after, firstEntry, lastEntry);
    return earlierUpdated || newerUpdated;
};

const messageWindowLoadingElementsMatch = (container: Element, visibility: MessageWindowLoadingVisibility, entries: readonly HTMLElement[]): boolean => {
    const inspection = inspectMessageWindowLoadingElements(container, entries);
    const existing = inspection.elements;
    const expectedCount = Number(visibility.showEarlier) + Number(visibility.showNewer);
    if (existing.length !== expectedCount) return false;
    if (entries.length === 0) {
        const expectedDirections: MessageWindowLoadingDirection[] = [];
        if (visibility.showEarlier) expectedDirections.push('before');
        if (visibility.showNewer) expectedDirections.push('after');
        return expectedDirections.every((direction, index) => {
            const element = existing[index];
            return element !== undefined && container.children[index] === element && requireMessageWindowLoadingLabel(element).textContent === resolveLoadingLabel(direction);
        });
    }
    const earlier = inspection.before;
    const newer = inspection.after;
    if ((earlier !== null) !== visibility.showEarlier || (newer !== null) !== visibility.showNewer) return false;
    if (earlier !== null && requireMessageWindowLoadingLabel(earlier).textContent !== resolveLoadingLabel('before')) return false;
    return newer === null || requireMessageWindowLoadingLabel(newer).textContent === resolveLoadingLabel('after');
};

export { messageWindowLoadingElementsMatch, renderMessageWindowLoadingMarkup, syncMessageWindowLoadingElements };

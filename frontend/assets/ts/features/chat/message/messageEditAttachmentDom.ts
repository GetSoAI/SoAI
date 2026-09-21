/* SoAI - Chat message edit attachment DOM controls [frontend/assets/ts/features/chat/message/messageEditAttachmentDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { optionalNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const EDIT_ATTACHMENT_INDEX_ATTRIBUTE = 'data-edit-attachment-index';
const EDIT_ATTACHMENT_REMOVED_ATTRIBUTE = 'data-edit-attachment-removed';
const EDIT_ATTACHMENT_RANGE_START_ATTRIBUTE = 'data-edit-attachment-range-start';
const EDIT_ATTACHMENT_RANGE_COUNT_ATTRIBUTE = 'data-edit-attachment-range-count';

const shouldCopyEditAttachmentAttribute = (name: string): boolean => {
    return name !== 'class' && name !== 'href' && name !== 'target' && name !== 'rel' && name !== 'type' && name !== 'data-action' && name !== 'data-href';
};

const normalizeEditAttachmentCard = (card: HTMLElement): HTMLElement => {
    if (!(card instanceof HTMLAnchorElement) && !(card instanceof HTMLButtonElement)) {
        return card;
    }
    const normalized = dom.getDocument().createElement('div');
    normalized.className = card.className;
    for (const attribute of Array.from(card.attributes)) {
        if (shouldCopyEditAttachmentAttribute(attribute.name)) {
            normalized.setAttribute(attribute.name, attribute.value);
        }
    }
    normalized.append(...Array.from(card.childNodes));
    card.replaceWith(normalized);
    return normalized;
};

const createEditAttachmentStrip = (messageTextNode: HTMLElement, removeIcon: TrustedHtml): HTMLElement | null => {
    const sourceStrip = dom.resolve('.message-attachment-strip', messageTextNode);
    if (!(sourceStrip instanceof HTMLElement)) {
        return null;
    }
    const strip = sourceStrip;
    strip.classList.add('message-edit-attachment-strip');
    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    const cards = dom.resolveAll('.chat-attachment-summary-card', strip);
    cards.forEach((card, index) => {
        if (!(card instanceof HTMLElement)) {
            return;
        }
        const normalizedCard = normalizeEditAttachmentCard(card);
        const hiddenCount = optionalNonNegativeIntegerAttribute(normalizedCard, 'data-hidden-attachment-count', 'Message edit attachment card');
        if (hiddenCount === null || hiddenCount === 0) {
            normalizedCard.setAttribute(EDIT_ATTACHMENT_INDEX_ATTRIBUTE, String(index));
        } else {
            normalizedCard.setAttribute(EDIT_ATTACHMENT_RANGE_START_ATTRIBUTE, String(index));
            normalizedCard.setAttribute(EDIT_ATTACHMENT_RANGE_COUNT_ATTRIBUTE, String(hiddenCount));
        }
        const button = dom.getDocument().createElement('button');
        button.type = 'button';
        button.className = 'remove-file-btn message-edit-remove-attachment-btn';
        button.setAttribute('aria-label', removeLabel);
        setTooltipText(button, removeLabel);
        replaceChildrenFromTrustedHtml({ element: button, html: removeIcon, context: button });
        normalizedCard.append(button);
    });
    return strip;
};

const renderEditTextareaMarkup = (): TrustedHtml => uiHtml`<textarea class="message-edit-input"></textarea>`;

const resolveRemovedEditAttachmentIndexes = (container: HTMLElement): number[] => {
    const removed = new Set<number>();
    for (const card of dom.resolveAll(`[${EDIT_ATTACHMENT_REMOVED_ATTRIBUTE}="1"][${EDIT_ATTACHMENT_INDEX_ATTRIBUTE}]`, container)) {
        if (!(card instanceof HTMLElement)) {
            continue;
        }
        const index = optionalNonNegativeIntegerAttribute(card, EDIT_ATTACHMENT_INDEX_ATTRIBUTE, 'Message edit attachment removal');
        if (index !== null) {
            removed.add(index);
        }
    }
    for (const card of dom.resolveAll(`[${EDIT_ATTACHMENT_REMOVED_ATTRIBUTE}="1"][${EDIT_ATTACHMENT_RANGE_START_ATTRIBUTE}][${EDIT_ATTACHMENT_RANGE_COUNT_ATTRIBUTE}]`, container)) {
        if (!(card instanceof HTMLElement)) {
            continue;
        }
        const startIndex = optionalNonNegativeIntegerAttribute(card, EDIT_ATTACHMENT_RANGE_START_ATTRIBUTE, 'Message edit attachment removal');
        const count = optionalNonNegativeIntegerAttribute(card, EDIT_ATTACHMENT_RANGE_COUNT_ATTRIBUTE, 'Message edit attachment removal');
        if (startIndex === null || count === null) {
            continue;
        }
        for (let offset = 0; offset < count; offset += 1) {
            removed.add(startIndex + offset);
        }
    }
    return Array.from(removed).sort((left, right) => left - right);
};

const hasRemainingEditAttachments = (container: HTMLElement): boolean => {
    for (const card of dom.resolveAll('.message-edit-attachment-strip .chat-attachment-summary-card', container)) {
        if (card instanceof HTMLElement && card.getAttribute(EDIT_ATTACHMENT_REMOVED_ATTRIBUTE) !== '1') {
            return true;
        }
    }
    return false;
};

const handleEditAttachmentClick = (container: HTMLElement, event: Event): boolean => {
    const target = event.target;
    if (!(target instanceof Element)) {
        return false;
    }
    const strip = target.closest('.message-edit-attachment-strip');
    if (!(strip instanceof HTMLElement) || !container.contains(strip)) {
        return false;
    }
    event.preventDefault();
    const removeButton = target.closest('.message-edit-remove-attachment-btn');
    if (!(removeButton instanceof HTMLButtonElement) || removeButton.disabled) {
        return true;
    }
    const card = removeButton.closest('.chat-attachment-summary-card');
    if (card instanceof HTMLElement) {
        card.setAttribute(EDIT_ATTACHMENT_REMOVED_ATTRIBUTE, '1');
        card.hidden = true;
    }
    return true;
};

export { createEditAttachmentStrip, handleEditAttachmentClick, hasRemainingEditAttachments, renderEditTextareaMarkup, resolveRemovedEditAttachmentIndexes };

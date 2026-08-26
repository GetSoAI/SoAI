/* SoAI - Conversation PDF export attachment card controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfAttachmentCardController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { middleEllipsisText } from '@core/primitives/text.ts';

const ATTACHMENT_CARD_SELECTOR = '.chat-attachment-summary-card';
const ATTACHMENT_CARD_NAME_SELECTOR = '.file-name';
const EXPORT_ATTACHMENT_FILENAME_MAX_LENGTH = 26;

const toStaticAttachmentCard = (card: HTMLElement): HTMLElement => {
    if (!(card instanceof HTMLButtonElement)) {
        return card;
    }
    const staticCard = card.ownerDocument.createElement('div');
    staticCard.className = card.className;
    staticCard.append(...Array.from(card.childNodes));
    card.replaceWith(staticCard);
    return staticCard;
};

const shortenAttachmentCardName = (card: HTMLElement): void => {
    const name = dom.resolve(ATTACHMENT_CARD_NAME_SELECTOR, card);
    if (!(name instanceof HTMLElement)) {
        return;
    }
    const label = toTrimmedString(name.textContent);
    if (!label) {
        return;
    }
    name.textContent = middleEllipsisText(label, EXPORT_ATTACHMENT_FILENAME_MAX_LENGTH);
};

const flattenConversationExportAttachmentCards = (container: HTMLElement): void => {
    for (const element of dom.resolveAll(ATTACHMENT_CARD_SELECTOR, container)) {
        if (!(element instanceof HTMLElement)) {
            continue;
        }
        shortenAttachmentCardName(toStaticAttachmentCard(element));
    }
};

export { flattenConversationExportAttachmentCards };

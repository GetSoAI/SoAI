/* SoAI - Chat feature inline multimedia media slot lifecycle [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaMediaSlotLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLAudioElementInOwnDocument, isHTMLElementInOwnDocument, isHTMLImageElementInOwnDocument, isHTMLVideoElementInOwnDocument } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { reconcileInlineMediaSlotLoadState, registerInlineMediaSlotLifecycle } from '@features/chat/message/enhancers/inlineMultimediaMediaSlot.ts';

const MEDIA_SLOT_SELECTOR = '.chat-inline-media-card__media';

class InlineMultimediaMediaSlotLifecycle {
    reconcile(root: HTMLElement): boolean {
        let changed = false;
        const slots = this.#collectMediaSlots(root);
        for (const slot of slots) {
            changed = this.#reconcileSlot(slot) || changed;
        }
        return changed;
    }

    #collectMediaSlots(root: HTMLElement): HTMLElement[] {
        const slots: HTMLElement[] = [];
        if (root.matches(MEDIA_SLOT_SELECTOR)) {
            slots.push(root);
        }
        for (const slot of dom.resolveAll(MEDIA_SLOT_SELECTOR, root)) {
            if (isHTMLElementInOwnDocument(slot)) {
                slots.push(slot);
            }
        }
        return slots;
    }

    #reconcileSlot(slot: HTMLElement): boolean {
        const mediaElement = this.#resolvePrimaryMediaElement(slot);
        if (mediaElement === null) {
            return false;
        }
        registerInlineMediaSlotLifecycle(slot, mediaElement);
        return reconcileInlineMediaSlotLoadState(slot, mediaElement);
    }

    #resolvePrimaryMediaElement(slot: HTMLElement): HTMLElement | null {
        for (const element of dom.resolveAll('img:not(.chat-inline-media-card__image--blurred-bg), audio, video', slot)) {
            if (isHTMLImageElementInOwnDocument(element) || isHTMLAudioElementInOwnDocument(element) || isHTMLVideoElementInOwnDocument(element)) {
                return element;
            }
        }
        return null;
    }
}

export { InlineMultimediaMediaSlotLifecycle };

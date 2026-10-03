/* SoAI - Stable chat model control reconciliation and presence lifecycle [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/chatModelControlReconcileController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { CHAT_MODEL_SLOTS_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';

const collectSlots = (container: HTMLElement): Map<string, HTMLElement> => {
    const slots = new Map<string, HTMLElement>();
    for (const child of Array.from(container.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains('chat-model-slot-wrap')) {
            throw new Error('Chat model slots require slot wrappers');
        }
        const button = dom.resolve('.chat-model-slot', child);
        const placeholder = child.classList.contains('chat-model-slot-wrap--placeholder');
        if (!(button instanceof HTMLButtonElement) || child.children.length !== (placeholder ? 1 : 2) || Array.from(child.children).some((control) => !(control instanceof HTMLButtonElement))) {
            throw new Error('Chat model slot wrappers require matching button controls');
        }
        const identity = placeholder ? 'placeholder' : button.getAttribute('data-slot-index');
        if (!identity || slots.has(identity)) {
            throw new Error('Chat model slots require unique slot identities');
        }
        slots.set(identity, child);
    }
    return slots;
};

const reconcileChatModelSlots = (currentContainer: HTMLElement, currentSlots: Map<string, HTMLElement>, nextSlots: Map<string, HTMLElement>): void => {
    for (const [identity, nextSlot] of nextSlots) {
        const currentSlot = currentSlots.get(identity);
        if (currentSlot) {
            insertWithPresence(currentContainer, currentSlot);
            syncElementShell({ target: currentSlot, source: nextSlot });
            for (let index = 0; index < nextSlot.children.length; index += 1) {
                const currentButton = currentSlot.children[index];
                const nextButton = nextSlot.children[index];
                if (!(currentButton instanceof HTMLElement) || !(nextButton instanceof HTMLElement)) {
                    throw new Error('Chat model slot reconciliation requires matching controls');
                }
                syncElementShell({ target: currentButton, source: nextButton });
                replaceChildrenIfChanged(currentButton, nextButton);
            }
        } else {
            insertWithPresence(currentContainer, nextSlot, identity === 'placeholder' ? null : (currentSlots.get('placeholder') ?? null));
        }
    }
    for (const [identity, currentSlot] of currentSlots) {
        if (!nextSlots.has(identity)) removeWithPresence(currentSlot);
    }
};

const reconcileChatModelControl = (currentControl: HTMLElement, nextControl: HTMLElement): void => {
    const currentContainer = dom.resolve(CHAT_MODEL_SLOTS_SELECTOR, currentControl);
    const nextContainer = dom.resolve(CHAT_MODEL_SLOTS_SELECTOR, nextControl);
    const currentPrimary = dom.resolve('.chat-model-control-primary', currentControl);
    const nextPrimary = dom.resolve('.chat-model-control-primary', nextControl);
    const currentSlots = currentContainer instanceof HTMLElement ? collectSlots(currentContainer) : new Map<string, HTMLElement>();
    const nextSlots = nextContainer instanceof HTMLElement ? collectSlots(nextContainer) : new Map<string, HTMLElement>();
    if (!(nextContainer instanceof HTMLElement) && !(nextPrimary instanceof HTMLButtonElement)) {
        throw new Error('Chat model controls require model slots or a primary button');
    }
    syncElementShell({ target: currentControl, source: nextControl });
    if (nextContainer instanceof HTMLElement) {
        if (currentContainer instanceof HTMLElement) {
            insertWithPresence(currentControl, currentContainer);
            syncElementShell({ target: currentContainer, source: nextContainer });
            reconcileChatModelSlots(currentContainer, currentSlots, nextSlots);
        } else {
            dom.appendChild(currentControl, nextContainer);
        }
        if (currentPrimary instanceof HTMLElement) removeWithPresence(currentPrimary);
        return;
    }
    if (nextPrimary instanceof HTMLButtonElement) {
        if (currentPrimary instanceof HTMLButtonElement) {
            insertWithPresence(currentControl, currentPrimary);
            syncElementShell({ target: currentPrimary, source: nextPrimary });
            replaceChildrenIfChanged(currentPrimary, nextPrimary);
        } else {
            insertWithPresence(currentControl, nextPrimary);
        }
    }
    if (currentContainer instanceof HTMLElement) {
        currentContainer.setAttribute('data-presence-atomic', '');
        currentContainer.setAttribute('data-presence-visual-only', '');
        removeWithPresence(currentContainer);
    }
};

export { reconcileChatModelControl };

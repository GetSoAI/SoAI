/* SoAI - Conversation find shortcuts, selection admission and focus return [frontend/assets/ts/pages/chat/controllers/conversationfind/interactionEventsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { captureConversationFindPrefill } from '@features/chat/public.ts';

interface ConversationFindInteractionHost {
    root: HTMLElement;
    wrapper: HTMLElement;
    input: HTMLInputElement;
    isOpen(): boolean;
    isActive(): boolean;
    hasModal(): boolean;
    isRenaming(): boolean;
    canOpen(): boolean;
    open(prefill: string | null, focus: HTMLElement | null): void;
    captureOpening(prefill: string | null, focus: HTMLElement | null): void;
    close(restoreFocus: boolean): void;
    queryChanged(): void;
    enter(backward: boolean): void;
    navigate(delta: number, wrap: boolean): void;
    cancelMovement(): void;
}

const bindConversationFindInteractions = (host: ConversationFindInteractionHost, signal: AbortSignal): void => {
    const documentRef = host.root.ownerDocument;
    documentRef.addEventListener(
        'keydown',
        (event) => {
            if (!host.isActive() || event.isComposing || event.keyCode === 229 || host.hasModal()) return;
            const command = event.ctrlKey !== event.metaKey && !event.altKey;
            if (command && !event.shiftKey && event.key.toLowerCase() === 'f') {
                if (host.isRenaming()) {
                    event.preventDefault();
                    return;
                }
                if (!host.isOpen() && !host.canOpen()) return;
                event.preventDefault();
                event.stopPropagation();
                if (event.repeat) return;
                if (host.isOpen()) host.close(true);
                else host.open(captureConversationFindPrefill(host.root), documentRef.activeElement instanceof HTMLElement ? documentRef.activeElement : null);
                return;
            }
            if (!host.isOpen()) return;
            const inside = event.target instanceof Node && host.wrapper.contains(event.target);
            if (inside && event.key === 'Escape' && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey) {
                event.preventDefault();
                event.stopPropagation();
                host.close(true);
            } else if ((command && event.key.toLowerCase() === 'g') || (event.key === 'F3' && !event.ctrlKey && !event.metaKey && !event.altKey)) {
                event.preventDefault();
                event.stopPropagation();
                host.navigate(event.shiftKey ? -1 : 1, true);
            } else if (event.target === host.input && event.key === 'Enter' && !event.ctrlKey && !event.metaKey && !event.altKey) {
                event.preventDefault();
                event.stopPropagation();
                host.enter(event.shiftKey);
            } else if (['PageUp', 'PageDown', 'Home', 'End', 'ArrowUp', 'ArrowDown', ' '].includes(event.key) && !inside && !(event.target instanceof Element && event.target.closest('input,textarea,[contenteditable]'))) {
                host.cancelMovement();
            }
        },
        { signal, capture: true }
    );
    host.root.addEventListener(
        'pointerdown',
        (event) => {
            if (!(event.target instanceof Element) || !event.target.closest('[data-action="chat:find-open"]')) return;
            host.captureOpening(captureConversationFindPrefill(host.root), documentRef.activeElement instanceof HTMLElement ? documentRef.activeElement : null);
            event.preventDefault();
        },
        { signal, capture: true }
    );
    const onQueryChanged = (): void => host.queryChanged();
    host.input.addEventListener('input', onQueryChanged, { signal, capture: true });
    host.input.addEventListener('compositionstart', onQueryChanged, { signal, capture: true });
    documentRef.addEventListener(
        'pointerdown',
        (event) => {
            if (!host.isOpen() || !(event.target instanceof Node) || host.wrapper.contains(event.target)) return;
            host.cancelMovement();
            if (!host.input.value.trim() && !(event.target instanceof Element && event.target.closest('[data-action="chat:find-open"]'))) host.close(false);
        },
        { signal, capture: true }
    );
    const area = dom.resolve('.chat-messages-area', host.root);
    const onUserScroll = (): void => host.cancelMovement();
    area?.addEventListener('wheel', onUserScroll, { signal, passive: true });
    area?.addEventListener('touchstart', onUserScroll, { signal, passive: true });
};

export { bindConversationFindInteractions };
export type { ConversationFindInteractionHost };

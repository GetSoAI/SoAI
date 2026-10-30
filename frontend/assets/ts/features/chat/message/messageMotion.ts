/* SoAI - Shared chat message motion helpers [frontend/assets/ts/features/chat/message/messageMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requestPresenceEnter } from '@core/animations/presence/public.ts';
import { resolveMaxCssAnimationTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';

const chatMessageEnterAnimationClass = 'fade-slide-in';
const CHAT_MESSAGE_ENTER_PRESERVED_CLASS_NAMES: ReadonlySet<string> = new Set([chatMessageEnterAnimationClass]);
const chatMessageDeletedExitAnimationClass = 'chat-message-deleted-exit';
const chatMessageAnimationCleanupBufferMs = 50;

type ChatMessageInsertAnimationOptions = {
    suppressInsertAnimations?: boolean;
};

const applySelfCleaningAnimationClass = (element: HTMLElement, className: string): void => {
    element.classList.add(className);
    const view = element.ownerDocument.defaultView;
    let timeoutId: number | null = null;
    let frameId: number | null = null;
    const cleanup = (): void => {
        element.removeEventListener('animationend', onEnd);
        if (timeoutId !== null) {
            view?.clearTimeout(timeoutId);
            timeoutId = null;
        }
        if (frameId !== null) {
            view?.cancelAnimationFrame(frameId);
            frameId = null;
        }
        element.classList.remove(className);
    };
    const onEnd = (event: AnimationEvent): void => {
        if (event.target === element) {
            cleanup();
        }
    };
    element.addEventListener('animationend', onEnd);
    if (view) {
        frameId = view.requestAnimationFrame(() => {
            frameId = null;
            timeoutId = view.setTimeout(cleanup, resolveMaxCssAnimationTotalMs(element) + chatMessageAnimationCleanupBufferMs);
        });
    }
};

const applyChatMessageEnterAnimation = (element: HTMLElement, options: ChatMessageInsertAnimationOptions = {}): void => {
    requestPresenceEnter(element, false);
    if (options.suppressInsertAnimations !== true) applySelfCleaningAnimationClass(element, chatMessageEnterAnimationClass);
};

const prefersReducedMotion = (element: Element): boolean => {
    const view = element.ownerDocument.defaultView;
    if (!view) {
        return false;
    }
    return view.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

const applyChatMessageDeletedExitAnimation = (element: HTMLElement, onAnimationEnd: () => void): boolean => {
    if (prefersReducedMotion(element)) {
        return false;
    }
    element.classList.add(chatMessageDeletedExitAnimationClass);
    element.addEventListener(
        'animationend',
        (event): void => {
            if (!(event.target instanceof HTMLElement) || !event.target.classList.contains('message-text')) {
                return;
            }
            onAnimationEnd();
        },
        { once: true }
    );
    return true;
};

export { applyChatMessageDeletedExitAnimation, applyChatMessageEnterAnimation, CHAT_MESSAGE_ENTER_PRESERVED_CLASS_NAMES, prefersReducedMotion };
export type { ChatMessageInsertAnimationOptions };

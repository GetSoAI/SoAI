/* SoAI - Nested thinking scroll ownership during opening motion [frontend/assets/ts/features/chat/message/inlineActivityDetailsOpeningScroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMainTimelineKeyboardScrollEvent } from '@features/chat/mainTimelineScroll.ts';
import { dom } from '@core/dom/dom.ts';

const followInlineActivityDetailsOpeningBottom = (details: HTMLElement): void => {
    details.scrollTop = details.scrollHeight;
    const animations = details.getAnimations();
    const windowRef = details.ownerDocument.defaultView;
    if (animations.length === 0 || windowRef === null) return;
    const lifetime = new AbortController();
    const observer = new windowRef.ResizeObserver(() => {
        if (!details.isConnected || details.parentElement?.getAttribute('data-collapsed') !== 'false') {
            stop();
            return;
        }
        if (!lifetime.signal.aborted) details.scrollTop = details.scrollHeight;
    });
    observer.observe(details);
    const content = dom.resolve('.message-thinking-phase', details);
    if (content instanceof HTMLElement) observer.observe(content);
    const stop = (): void => {
        observer.disconnect();
        lifetime.abort();
    };
    for (const type of ['wheel', 'touchstart', 'pointerdown']) details.addEventListener(type, stop, { passive: true, signal: lifetime.signal });
    details.addEventListener(
        'keydown',
        (event) => {
            if (isMainTimelineKeyboardScrollEvent(event)) stop();
        },
        { passive: true, signal: lifetime.signal }
    );
    const settle = (): void => {
        if (animations.some((animation) => animation.playState === 'running' || animation.playState === 'paused')) return;
        if (!lifetime.signal.aborted && details.isConnected && details.parentElement?.getAttribute('data-collapsed') === 'false') details.scrollTop = details.scrollHeight;
        stop();
    };
    for (const animation of animations) {
        animation.addEventListener('finish', settle, { once: true, signal: lifetime.signal });
        animation.addEventListener('cancel', settle, { once: true, signal: lifetime.signal });
    }
    settle();
};

export { followInlineActivityDetailsOpeningBottom };

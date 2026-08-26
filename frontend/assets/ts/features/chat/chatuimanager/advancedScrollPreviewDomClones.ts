/* SoAI - Advanced scroll preview DOM snapshot ownership [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewDomClones.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncStyleProperty } from '@core/dom/patching.ts';

const MINIMAP_LINE_HEIGHT_PX = 2;
const MINIMAP_LINE_PITCH_PX = 7;

type MinimapCloneLayout = {
    topPx: number;
    heightPx: number;
};

const mutationTouchesMessageList = (mutation: MutationRecord, messagesRoot: HTMLElement): boolean => {
    if (mutation.type === 'childList' && mutation.target === messagesRoot) {
        return true;
    }
    if (mutation.type !== 'attributes' || mutation.attributeName !== 'class' || !(mutation.target instanceof HTMLElement) || mutation.target.parentElement !== messagesRoot) {
        return false;
    }
    const previousClasses = new Set((mutation.oldValue ?? '').split(/\s+/).filter(Boolean));
    return mutation.target.classList.contains('chat-message') || mutation.target.classList.contains('chat-comparison-turn') || previousClasses.has('chat-message') || previousClasses.has('chat-comparison-turn');
};

const resolveRoleClass = (source: HTMLElement): 'user' | 'assistant' | 'system' => {
    if (source.classList.contains('user')) {
        return 'user';
    }
    if (source.classList.contains('assistant') || source.classList.contains('chat-comparison-turn')) {
        return 'assistant';
    }
    return 'system';
};

const resolveMinimapMessageHeightPx = (heightPx: number): number => {
    if (!Number.isFinite(heightPx)) {
        return 8;
    }
    return Math.max(8, Math.ceil(heightPx));
};

const resolveMinimapLineWidth = (height: number): number => {
    if (height <= 14) {
        return 42;
    }
    if (height <= 28) {
        return 58;
    }
    if (height <= 56) {
        return 72;
    }
    return 86;
};

const resolveMinimapCloneStateSignature = (source: HTMLElement, layout: MinimapCloneLayout): string => {
    const roleClass = resolveRoleClass(source);
    const height = resolveMinimapMessageHeightPx(layout.heightPx);
    return `${roleClass}|${source.hidden ? '1' : '0'}|${String(Math.max(0, Math.floor(layout.topPx)))}|${String(height)}`;
};

const syncMinimapLineMarker = (target: HTMLElement, source: HTMLElement, height: number): void => {
    const existing = target.firstElementChild;
    const marker = existing instanceof HTMLSpanElement ? existing : source.ownerDocument.createElement('span');
    syncStyleProperty(marker, 'width', `${resolveMinimapLineWidth(height)}%`);
    syncStyleProperty(marker, 'height', `${height}px`);
    syncStyleProperty(marker, 'background', `repeating-linear-gradient(to bottom, currentColor 0 ${MINIMAP_LINE_HEIGHT_PX}px, transparent ${MINIMAP_LINE_HEIGHT_PX}px ${MINIMAP_LINE_PITCH_PX}px)`);
    if (marker.parentElement !== target) {
        target.replaceChildren(marker);
    }
};

const syncMinimapCloneState = (target: HTMLElement, source: HTMLElement, layout: MinimapCloneLayout): void => {
    const roleClass = resolveRoleClass(source);
    const height = resolveMinimapMessageHeightPx(layout.heightPx);
    const className = `chat-advanced-scroll-minimap-message ${roleClass}`;
    if (target.className !== className) {
        target.className = className;
    }
    if (target.hidden !== source.hidden) {
        target.hidden = source.hidden;
    }
    syncStyleProperty(target, 'top', `${Math.max(0, Math.floor(layout.topPx))}px`);
    syncStyleProperty(target, 'height', `${height}px`);
    syncMinimapLineMarker(target, source, height);
};

const cloneMinimapMessage = (source: HTMLElement, layout: MinimapCloneLayout): HTMLElement => {
    const marker = source.ownerDocument.createElement('div');
    syncMinimapCloneState(marker, source, layout);
    return marker;
};

const patchMinimapCloneInPlace = (target: HTMLElement, source: HTMLElement, layout: MinimapCloneLayout): void => {
    syncMinimapCloneState(target, source, layout);
};

export { cloneMinimapMessage, mutationTouchesMessageList, patchMinimapCloneInPlace, resolveMinimapCloneStateSignature };
export type { MinimapCloneLayout };

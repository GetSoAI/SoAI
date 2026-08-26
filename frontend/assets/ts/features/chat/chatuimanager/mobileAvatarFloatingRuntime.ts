/* SoAI - Mobile chat avatar floating-state frame runtime [frontend/assets/ts/features/chat/chatuimanager/mobileAvatarFloatingRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX } from '@features/chat/chatConstants.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';

type AvatarMessagePair = {
    avatar: HTMLElement;
    message: HTMLElement;
};

type AvatarFloatingMeasurement = {
    avatar: HTMLElement;
    floating: boolean;
};

type MobileAvatarFloatingRuntime = {
    schedule: () => void;
    syncImmediately: () => void;
    dispose: () => void;
};

const AVATAR_FLOATING_CLASS = 'is-floating';
const AVATAR_SELECTOR = '.chat-message > .message-avatar';
const FRAME_KEY = 'mobile-avatar-floating';

const classMutationChangesSelectorMembership = (mutation: MutationRecord): boolean => {
    if (mutation.type !== 'attributes' || mutation.attributeName !== 'class' || !(mutation.target instanceof HTMLElement)) {
        return false;
    }
    const oldClasses = new Set((mutation.oldValue ?? '').split(/\s+/).filter(Boolean));
    const wasAvatar = oldClasses.has('message-avatar');
    const isAvatar = mutation.target.classList.contains('message-avatar');
    const wasMessage = oldClasses.has('chat-message');
    const isMessage = mutation.target.classList.contains('chat-message');
    return wasAvatar !== isAvatar || wasMessage !== isMessage;
};

const nodeContainsAvatarStructure = (node: Node): boolean => {
    if (!(node instanceof Element)) {
        return false;
    }
    if (node.classList.contains('message-avatar') || node.classList.contains('chat-message')) {
        return true;
    }
    return dom.resolve('.message-avatar, .chat-message', node) !== null;
};

const mutationChangesAvatarStructure = (mutation: MutationRecord): boolean => {
    if (classMutationChangesSelectorMembership(mutation)) {
        return true;
    }
    if (mutation.type !== 'childList') {
        return false;
    }
    return [...Array.from(mutation.addedNodes), ...Array.from(mutation.removedNodes)].some(nodeContainsAvatarStructure);
};

const createMobileAvatarFloatingRuntime = (messagesArea: HTMLElement, messagesRoot: HTMLElement): MobileAvatarFloatingRuntime => {
    const coordinator = acquireMainTimelineCoordinator(messagesArea, messagesRoot);
    let cachedPairs: readonly AvatarMessagePair[] | null = null;
    let isDisposed = false;

    const resolvePairs = (): readonly AvatarMessagePair[] => {
        if (cachedPairs) {
            return cachedPairs;
        }
        const pairs: AvatarMessagePair[] = [];
        for (const candidate of dom.resolveAll(AVATAR_SELECTOR, messagesArea)) {
            if (candidate instanceof HTMLElement && candidate.parentElement instanceof HTMLElement) {
                pairs.push({ avatar: candidate, message: candidate.parentElement });
            }
        }
        cachedPairs = pairs;
        return pairs;
    };

    const measure = (): readonly AvatarFloatingMeasurement[] | null => {
        if (isDisposed || measureLayoutViewport(messagesArea).width > CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX || !messagesArea.isConnected) {
            return null;
        }
        const containerTop = measureLayoutBox(messagesArea).top;
        return resolvePairs().map(({ avatar, message }) => {
            const messageRect = measureLayoutBox(message);
            return {
                avatar,
                floating: messageRect.top < containerTop && messageRect.bottom > containerTop
            };
        });
    };

    const apply = (measurements: readonly AvatarFloatingMeasurement[] | null): void => {
        if (!measurements || isDisposed) {
            return;
        }
        for (const measurement of measurements) {
            measurement.avatar.classList.toggle(AVATAR_FLOATING_CLASS, measurement.floating);
        }
    };

    const schedule = (): void => {
        if (isDisposed || measureLayoutViewport(messagesArea).width > CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX) {
            return;
        }
        coordinator.scheduleFrame(FRAME_KEY, () => {
            const measurements = measure();
            return measurements ? () => apply(measurements) : null;
        });
    };

    const mutationDisposer = coordinator.subscribeMutations((mutations) => {
        if (mutations.some(mutationChangesAvatarStructure)) {
            cachedPairs = null;
        }
    });

    return {
        schedule,
        syncImmediately: () => apply(measure()),
        dispose: () => {
            if (isDisposed) {
                return;
            }
            isDisposed = true;
            coordinator.cancelFrame(FRAME_KEY);
            mutationDisposer();
            cachedPairs = null;
            coordinator.release();
        }
    };
};

export { createMobileAvatarFloatingRuntime };
export type { MobileAvatarFloatingRuntime };

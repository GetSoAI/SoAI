/* SoAI - Coordinated inline activity and header layout motion [frontend/assets/ts/features/chat/message/messageview/inlineActivityLayoutMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animatePresenceMorph, isPresenceAnimating, isPresenceMorphing, measurePresenceSize, stopPresenceAnimation, type PresenceSize } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';

interface InlineActivityLayout {
    size: PresenceSize;
    header: { element: HTMLElement; size: PresenceSize } | null;
}

const measureInlineActivityLayout = (activity: HTMLElement): InlineActivityLayout | null => {
    const size = measurePresenceSize(activity);
    if (size === null) return null;
    const header = dom.resolve(':scope > .inline-activity-header', activity);
    const headerBox = header instanceof HTMLElement ? measureLayoutBox(header) : null;
    return { size, header: header instanceof HTMLElement && headerBox !== null && headerBox.width > 0 && headerBox.height > 0 ? { element: header, size: { width: headerBox.width, height: headerBox.height } } : null };
};

const stopInlineActivityLayoutMotion = (activity: HTMLElement): void => {
    const header = dom.resolve(':scope > .inline-activity-header', activity);
    if (header instanceof HTMLElement) stopPresenceAnimation(header);
    stopPresenceAnimation(activity);
};

const animateInlineActivityWidth = (activity: HTMLElement, previous: InlineActivityLayout | null): Animation | null => {
    stopInlineActivityLayoutMotion(activity);
    const next = measureInlineActivityLayout(activity);
    if (previous === null || next === null) return null;
    const headerAnimation = previous.header !== null && next.header !== null && previous.header.element === next.header.element ? animatePresenceMorph(next.header.element, { width: previous.header.size.width, height: next.header.size.height }, next.header.size, { fadeChildren: false, preserveWrapping: true, preserveChildInlineSize: true }) : null;
    const animation = animatePresenceMorph(activity, { width: previous.size.width, height: next.size.height }, next.size, { fadeChildren: false, preserveWrapping: true });
    if (animation !== null && headerAnimation !== null) headerAnimation.startTime = animation.startTime;
    return animation ?? headerAnimation;
};

const patchInlineActivityLayoutWithMotion = (element: HTMLElement, patch: () => boolean): boolean => {
    const parent = element.closest('.inline-activity');
    const activity = parent instanceof HTMLElement && parent.getAttribute('data-collapsed') === 'true' && (!isPresenceAnimating(parent) || isPresenceMorphing(parent)) ? parent : null;
    const previous = activity === null ? null : measureInlineActivityLayout(activity);
    const changed = patch();
    if (changed && activity !== null && previous !== null) animateInlineActivityWidth(activity, previous);
    return changed;
};

export { animateInlineActivityWidth, measureInlineActivityLayout, patchInlineActivityLayoutWithMotion, stopInlineActivityLayoutMotion };
export type { InlineActivityLayout };

/* SoAI - Sequenced inline activity width and details motion [frontend/assets/ts/features/chat/message/inlineActivityDetailsMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animateInlineActivityWidth, measureInlineActivityLayout, stopInlineActivityLayoutMotion, type InlineActivityLayout } from '@features/chat/message/messageview/inlineActivityLayoutMotion.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import { resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';

interface DetailsMotion {
    controller: AbortController;
    phase: 'opening' | 'closing';
}

const INLINE_ACTIVITY_DETAILS_EXPANDING_ATTRIBUTE = 'data-details-expanding';
const motionByActivity = new WeakMap<HTMLElement, DetailsMotion>();

const cancelInlineActivityDetailsMotion = (activity: HTMLElement): void => {
    const state = motionByActivity.get(activity);
    if (state !== undefined) {
        motionByActivity.delete(activity);
        state.controller.abort();
        stopInlineActivityLayoutMotion(activity);
    }
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_EXPANDING_ATTRIBUTE);
    activity.removeAttribute('data-collapsing');
};

const observeDetailsMotion = (activity: HTMLElement, state: DetailsMotion, target: HTMLElement, animations: Animation[], complete: () => void): void => {
    const finish = (): void => {
        if (motionByActivity.get(activity) !== state) return;
        complete();
    };
    void waitForElementAnimations(target, { ensureStarted: false, signal: state.controller.signal, animations }).then(finish, (error) => {
        if (!isAbortError(error)) errorHandler.warn('InlineActivityDetails', 'Activity animation did not complete', ensureError(error));
        finish();
    });
};

const animateDetailsWidth = (activity: HTMLElement, previousSize: InlineActivityLayout | null, state: DetailsMotion, complete: () => void): void => {
    const animation = animateInlineActivityWidth(activity, previousSize);
    if (animation === null) complete();
    else observeDetailsMotion(activity, state, activity, [animation], complete);
};

const openInlineActivityDetailsWithMotion = (activity: HTMLElement, commit: () => void, reveal: () => void): void => {
    const details = resolveDirectInlineActivityDetailsRoot(activity);
    if (activity.getAttribute('data-collapsed') !== 'true' || details === null) {
        commit();
        return;
    }
    if (motionByActivity.get(activity)?.phase === 'closing' && activity.hasAttribute('data-collapsing')) {
        cancelInlineActivityDetailsMotion(activity);
        commit();
        if (activity.isConnected) reveal();
        return;
    }
    const previousSize = measureInlineActivityLayout(activity);
    void details.offsetHeight;
    cancelInlineActivityDetailsMotion(activity);
    const state: DetailsMotion = { controller: new AbortController(), phase: 'opening' };
    motionByActivity.set(activity, state);
    activity.setAttribute(INLINE_ACTIVITY_DETAILS_EXPANDING_ATTRIBUTE, 'true');
    commit();
    animateDetailsWidth(activity, previousSize, state, () => {
        cancelInlineActivityDetailsMotion(activity);
        if (activity.isConnected && activity.getAttribute('data-collapsed') === 'false') reveal();
    });
};

const closeInlineActivityDetailsWithMotion = (activity: HTMLElement): void => {
    const previousSize = measureInlineActivityLayout(activity);
    const wasExpanding = activity.hasAttribute(INLINE_ACTIVITY_DETAILS_EXPANDING_ATTRIBUTE);
    const details = resolveDirectInlineActivityDetailsRoot(activity);
    cancelInlineActivityDetailsMotion(activity);
    const state: DetailsMotion = { controller: new AbortController(), phase: 'closing' };
    motionByActivity.set(activity, state);
    const shrink = (): void => {
        const from = wasExpanding ? previousSize : measureInlineActivityLayout(activity);
        activity.removeAttribute('data-collapsing');
        animateDetailsWidth(activity, from, state, () => cancelInlineActivityDetailsMotion(activity));
    };
    activity.setAttribute('data-collapsed', 'true');
    if (details === null || wasExpanding || isReducedAnimationScope(activity)) {
        shrink();
        return;
    }
    activity.setAttribute('data-collapsing', 'true');
    void details.offsetHeight;
    const animations = details.getAnimations();
    if (animations.length === 0) shrink();
    else observeDetailsMotion(activity, state, details, animations, shrink);
};

const isInlineActivityDetailsClosing = (activity: HTMLElement): boolean => motionByActivity.get(activity)?.phase === 'closing';

export { INLINE_ACTIVITY_DETAILS_EXPANDING_ATTRIBUTE, cancelInlineActivityDetailsMotion, closeInlineActivityDetailsWithMotion, isInlineActivityDetailsClosing, openInlineActivityDetailsWithMotion };

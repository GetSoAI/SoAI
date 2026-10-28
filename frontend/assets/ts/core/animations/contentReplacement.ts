/* SoAI - Sequential content replacement fades [frontend/assets/ts/core/animations/contentReplacement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';

interface ContentReplacement {
    value: string;
    commit(value: string): void;
    animation: Animation | null;
    timer: ReturnType<typeof setTimeout> | null;
    phase: 'out' | 'in';
    restingOpacity: string;
}

const replacements = new WeakMap<Element, ContentReplacement>();

const replaceContentWithFade = (element: Element, value: string, commit: (value: string) => void, currentValue: string | null = element.textContent): boolean => {
    const current = replacements.get(element);
    if ((current?.value ?? currentValue) === value) return false;
    const view = element.ownerDocument.defaultView;
    const style = view?.getComputedStyle(element);
    const duration = isReducedAnimationScope(element) ? 0 : parseMaxCssDurationMs(style?.getPropertyValue('--motion-content-replacement-duration') ?? '');
    const clear = (state: ContentReplacement): void => {
        if (state.timer !== null) clearTimeout(state.timer);
        state.timer = null;
        const animation = state.animation;
        state.animation = null;
        animation?.cancel();
    };
    if (!element.isConnected || !view || duration === 0 || typeof element.animate !== 'function') {
        replacements.delete(element);
        if (current) clear(current);
        commit(value);
        return true;
    }
    if (current?.phase === 'out') {
        current.value = value;
        current.commit = commit;
        return true;
    }
    const opacity = style?.opacity ?? '1';
    if (current) clear(current);
    const restingOpacity = current?.restingOpacity ?? view.getComputedStyle(element).opacity;
    const state: ContentReplacement = { value, commit, animation: null, timer: null, phase: 'out', restingOpacity };
    replacements.set(element, state);
    const play = (phase: 'out' | 'in', from: string, to: string): void => {
        state.phase = phase;
        let animation: Animation;
        try {
            animation = element.animate([{ opacity: from }, { opacity: to }], { duration, easing: 'ease-in-out', fill: 'both' });
        } catch (error) {
            errorHandler.warn('ContentReplacement', 'Unable to animate content replacement', ensureError(error));
            replacements.delete(element);
            state.commit(state.value);
            return;
        }
        state.animation = animation;
        const finish = (): void => {
            if (replacements.get(element) !== state || state.animation !== animation) return;
            clear(state);
            if (phase === 'out') {
                state.commit(state.value);
                play('in', '0', restingOpacity);
            } else {
                replacements.delete(element);
            }
        };
        state.timer = setTimeout(finish, duration + 50);
        terminateHandledPromise(animation.finished.then(finish, finish));
    };
    play('out', opacity, '0');
    return true;
};

export { replaceContentWithFade };

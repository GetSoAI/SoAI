/* SoAI - Finite power mode surface motion [frontend/assets/ts/features/power/motion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';

class PowerModeMotion {
    readonly #animations = new Set<Animation>();
    readonly #exitScope = new LifecycleScope();

    #animate(element: HTMLElement, frames: Keyframe[], phase: 'enter' | 'exit'): Animation | null {
        const view = element.ownerDocument.defaultView;
        if (!view) throw new Error('Power mode requires an owning window');
        if (element.ownerDocument.visibilityState === 'hidden') return null;
        const style = view.getComputedStyle(element);
        const duration = scaleAnimationDurationMs(parseMaxCssDurationMs(style.getPropertyValue(phase === 'enter' ? '--presence-enter-duration' : '--presence-exit-duration')), element);
        if (!duration) return null;
        const animation = element.animate(frames, { duration, easing: style.getPropertyValue(phase === 'enter' ? '--presence-enter-ease' : '--presence-exit-ease').trim(), fill: phase === 'exit' ? 'both' : 'backwards' });
        this.#animations.add(animation);
        const forget = (): void => {
            this.#animations.delete(animation);
        };
        animation.addEventListener('cancel', forget, { once: true });
        if (phase === 'enter') animation.addEventListener('finish', forget, { once: true });
        return animation;
    }

    enter(modal: HTMLElement): void {
        this.stop();
        this.#animate(requireRootHTMLElement(modal, '.modal-overlay', 'Power backdrop'), [{ backdropFilter: 'grayscale(0)' }, { backdropFilter: 'grayscale(1)' }], 'enter');
        this.#animate(requireRootHTMLElement(modal, '.power-mode-surface', 'Power surface'), [{ opacity: 0 }, { opacity: 1 }], 'enter');
        this.#animate(
            requireRootHTMLElement(modal, '.power-mode-menu-glyph', 'Power menu glyph'),
            [
                { opacity: 1, transform: 'none' },
                { opacity: 0, transform: 'rotate(-45deg)' }
            ],
            'enter'
        );
        this.#animate(
            requireRootHTMLElement(modal, '.power-mode-back-glyph', 'Power Back glyph'),
            [
                { opacity: 0, transform: 'rotate(45deg)' },
                { opacity: 1, transform: 'none' }
            ],
            'enter'
        );
        const chooser = requireRootHTMLElement(modal, '.power-mode-chooser', 'Power chooser');
        this.#animate(
            chooser,
            [
                { opacity: 0, transform: 'translateY(var(--space-2))' },
                { opacity: 1, transform: 'none' }
            ],
            'enter'
        );
    }

    async exit(modal: HTMLElement): Promise<void> {
        const surface = requireRootHTMLElement(modal, '.power-mode-surface', 'Power surface');
        const chooser = requireRootHTMLElement(modal, '.power-mode-chooser', 'Power chooser');
        const view = modal.ownerDocument.defaultView;
        if (!view) throw new Error('Power mode requires an owning window');
        const targets = [
            { element: surface, opacity: '0', transform: null },
            { element: chooser, opacity: '0', transform: null },
            { element: requireRootHTMLElement(modal, '.power-mode-menu-glyph', 'Power menu glyph'), opacity: '1', transform: 'none' },
            { element: requireRootHTMLElement(modal, '.power-mode-back-glyph', 'Power Back glyph'), opacity: '0', transform: 'rotate(45deg)' }
        ].map((target) => {
            const style = view.getComputedStyle(target.element);
            return {
                element: target.element,
                frames: [
                    { opacity: style.opacity, transform: style.transform },
                    { opacity: target.opacity, transform: target.transform ?? style.transform }
                ]
            };
        });
        const backdrop = requireRootHTMLElement(modal, '.modal-overlay', 'Power backdrop');
        const backdropFrames = [{ backdropFilter: view.getComputedStyle(backdrop).backdropFilter }, { backdropFilter: 'grayscale(0)' }];
        this.stop();
        const run = this.#exitScope.begin('power-exit-superseded');
        const animations = [this.#animate(backdrop, backdropFrames, 'exit'), ...targets.map((target) => this.#animate(target.element, target.frames, 'exit'))].filter((animation): animation is Animation => animation !== null);
        try {
            await waitForElementAnimations(modal, { ensureStarted: false, signal: run.signal, animations });
        } catch (error) {
            if (!isAbortError(error)) throw ensureError(error);
        } finally {
            for (const animation of animations) {
                animation.cancel();
                this.#animations.delete(animation);
            }
        }
    }

    stop(): void {
        this.#exitScope.abort('power-motion-stop');
        for (const animation of this.#animations) animation.cancel();
        this.#animations.clear();
    }
}

export { PowerModeMotion };

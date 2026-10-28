/* SoAI - Wizard surface resize motion [frontend/assets/ts/pages/wizard/controllers/WizardMotionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animatePresenceMorph, isPresenceAnimating, measurePresenceSize, stopPresenceAnimation, type PresenceSize } from '@core/animations/presence/public.ts';
import { requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { scrollElementIntoView } from '@core/scroll.ts';

class WizardMotionController {
    readonly #card: HTMLElement;
    readonly #mutations: MutationObserver;
    readonly #sizes: ResizeObserver;
    #size: PresenceSize | null;
    readonly #frames = new ResourceTracker();
    #scheduled = false;

    constructor(root: HTMLElement, signal: AbortSignal) {
        this.#card = requireRootHTMLElement(root, '.wizard-card', 'Wizard card');
        this.#size = measurePresenceSize(this.#card);
        this.#mutations = new MutationObserver(() => {
            if (this.#scheduled) return;
            this.#scheduled = true;
            this.#frames.requestAnimationFrame(() => {
                this.#scheduled = false;
                this.#resize();
            });
        });
        this.#sizes = new ResizeObserver(() => {
            if (!isPresenceAnimating(this.#card)) this.#size = measurePresenceSize(this.#card);
        });
        this.#mutations.observe(this.#card, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class', 'hidden'] });
        this.#sizes.observe(this.#card);
        root.addEventListener('transitionend', this.#reveal, { signal });
        signal.addEventListener(
            'abort',
            () => {
                this.#frames.cleanup();
                this.#mutations.disconnect();
                this.#sizes.disconnect();
                stopPresenceAnimation(this.#card);
            },
            { once: true }
        );
    }

    #resize(): void {
        const previous = isPresenceAnimating(this.#card) ? measurePresenceSize(this.#card) : this.#size;
        const next = measurePresenceSize(this.#card);
        if (previous?.height === next?.height && previous?.width === next?.width) return;
        stopPresenceAnimation(this.#card);
        this.#size = next;
        if (previous !== null && next !== null && this.#card.isConnected) animatePresenceMorph(this.#card, previous, next, { fadeChildren: false, preserveWrapping: true });
    }

    readonly #reveal = (event: TransitionEvent): void => {
        const target = event.target;
        if (event.propertyName !== 'grid-template-rows' || !(target instanceof HTMLElement) || !target.matches('.wizard-reveal-region.is-expanded')) return;
        scrollElementIntoView(target);
    };
}

export { WizardMotionController };

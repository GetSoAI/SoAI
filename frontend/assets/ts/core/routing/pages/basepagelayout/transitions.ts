/* SoAI - Shared routing transitions [frontend/assets/ts/core/routing/pages/basepagelayout/transitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { request } from '@core/routing/pages/basepagecore/actions.ts';
import { PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN, PAGE_TRANSITION_MODE_ATTRIBUTE } from '@core/pageTransitions.ts';
import { getPageHeaderAnimator } from '@core/animations/service.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';

interface PageTransitionClassHost {
    removeClassName(target: Element, className: string): void;
    flushDOMUpdates(): void;
    getUI(selector: string | Element): Element | null;
}

const onHide = async (host: PageTransitionClassHost, section: Element | null): Promise<void> => {
    if (section) {
        host.removeClassName(section, PAGE_CONTENT_READY);
        host.removeClassName(section, PAGE_TRANSITIONING_IN);
        section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
        host.flushDOMUpdates();
    }
};

const attachHeaderAnimator = (host: PageTransitionClassHost): void => {
    const animator = request(getPageHeaderAnimator(), 'Anim');
    getRequestAnimationFrame()(() => {
        const container = host.getUI('.page-scrollable');
        if (container instanceof HTMLElement) {
            animator.attach(container);
        }
    });
};

export { onHide, attachHeaderAnimator };

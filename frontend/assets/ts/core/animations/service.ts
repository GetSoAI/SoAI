/* SoAI - Shared animations service [frontend/assets/ts/core/animations/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PageHeaderAnimator } from '@core/animations/events.ts';
import { type PageHeaderAnimatorProxy } from '@core/animations/types.ts';

interface AnimationsState {
    pageHeaderAnimator: PageHeaderAnimator | null;
}

class Animations {
    #state: AnimationsState;

    constructor() {
        this.#state = { pageHeaderAnimator: null };
    }

    getPageHeaderAnimator(): PageHeaderAnimator {
        if (!this.#state.pageHeaderAnimator) {
            this.#state.pageHeaderAnimator = new PageHeaderAnimator();
        }
        return this.#state.pageHeaderAnimator;
    }
}

let animationsInstance: Animations | null = null;

const getAnimations = (): Animations => {
    if (animationsInstance === null) {
        animationsInstance = new Animations();
    }
    return animationsInstance;
};

const getPageHeaderAnimator = (): PageHeaderAnimatorProxy => getAnimations().getPageHeaderAnimator();

export { Animations, getAnimations, getPageHeaderAnimator };
export type { PageHeaderAnimatorProxy };

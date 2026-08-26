/* SoAI - Routed page collapsible-card state and interaction ownership [frontend/assets/ts/core/routing/pages/basepagelayout/PageCollapsibleCards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { configureCardCollapse, type CollapsibleCardDependencies, type CollapsibleCardState } from '@core/routing/pages/basepagecollections/events.ts';
import type { CollapseController, CollapseControllerOptions } from '@core/routing/pages/pagetypes/public.ts';

interface PageCollapsibleCardsContract {
    configure(options?: CollapseControllerOptions): CollapseController;
    get(key: string): CollapseController;
    toggle(key: string): void;
    reset(): void;
}

class PageCollapsibleCards implements PageCollapsibleCardsContract {
    readonly #dependencies: CollapsibleCardDependencies;
    readonly #state: CollapsibleCardState = { controllers: new Map() };

    constructor(dependencies: CollapsibleCardDependencies) {
        this.#dependencies = dependencies;
    }

    configure(options: CollapseControllerOptions = {}): CollapseController {
        return configureCardCollapse(this.#dependencies, this.#state, options);
    }

    get(key: string): CollapseController {
        if (!key) {
            throw err('Key required');
        }
        const controller = this.#state.controllers.get(key);
        if (!controller) {
            throw err(`Controller "${key}" missing`);
        }
        return controller;
    }

    toggle(key: string): void {
        this.get(key).toggle();
    }

    reset(): void {
        this.#state.controllers.clear();
    }
}

export { PageCollapsibleCards };
export interface PageCollapsibleCardsOwnerHost {
    collapsibleCards: PageCollapsibleCardsContract;
}
export type { PageCollapsibleCardsContract };

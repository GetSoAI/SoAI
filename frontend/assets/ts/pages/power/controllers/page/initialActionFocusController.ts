/* SoAI - Power initial action focus handling [frontend/assets/ts/pages/power/controllers/page/initialActionFocusController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scrollElementIntoView } from '@core/scroll.ts';
import { isPowerActionId } from '@pages/power/actions.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface PowerInitialActionFocusHost extends PageDomOwnerHost {
    router: {
        getRouteParameters(): Record<string, string>;
    } | null;
}

const focusPowerInitialAction = (host: PowerInitialActionFocusHost, root: HTMLElement): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Power initial action focus requires a router');
    }
    const action = router.getRouteParameters()['action'] ?? '';
    if (!isPowerActionId(action)) {
        return;
    }
    const card = host.pageDom.optionalHTMLElement(`[data-action-key="${action}"]`, root);
    if (!card) {
        throw new Error(`Power action card not found for "${action}"`);
    }
    if (card.tabIndex < 0) {
        card.tabIndex = -1;
    }
    scrollElementIntoView(card, { block: 'center' });
    card.focus({ preventScroll: true });
};

export { focusPowerInitialAction };

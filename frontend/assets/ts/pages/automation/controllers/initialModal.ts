/* SoAI - Automation initial modal query handling [frontend/assets/ts/pages/automation/controllers/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { consumeRouteQuery, INITIAL_MODAL_QUERY_KEYS } from '@core/routeregistry/reconstruction.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import { AUTOMATION_ACTION_OPEN_CREATE_MODAL, type AutomationActionId } from '@features/automation/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface AutomationInitialModalHost extends PageDomOwnerHost {
    router: Pick<PageRouting, 'getRouteParameters' | 'getCurrentRoute' | 'getQueryParameters' | 'replaceCurrentRoute'> | null;
}

interface AutomationInitialModalController {
    handleAction(actionId: AutomationActionId, element: HTMLElement): void;
}

const clearAutomationInitialModalQuery = (host: AutomationInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Automation initial modal cleanup requires a router');
    }
    consumeRouteQuery(router, INITIAL_MODAL_QUERY_KEYS);
};

const handleAutomationInitialModal = (host: AutomationInitialModalHost, controller: AutomationInitialModalController, modal: string | null): void => {
    if (modal !== 'add-automation') {
        return;
    }
    controller.handleAction(AUTOMATION_ACTION_OPEN_CREATE_MODAL, host.pageDom.requireHTMLElement('#automation-create-button'));
    clearAutomationInitialModalQuery(host);
};

export { handleAutomationInitialModal };

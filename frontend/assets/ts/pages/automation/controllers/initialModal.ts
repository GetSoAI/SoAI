/* SoAI - Automation initial modal query handling [frontend/assets/ts/pages/automation/controllers/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildRouteWithoutQueryParameters } from '@core/routing/router/events.ts';
import { AUTOMATION_ACTION_OPEN_CREATE_MODAL, type AutomationActionId } from '@features/automation/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface AutomationInitialModalHost extends PageDomOwnerHost {
    router: {
        getRouteParameters(): Record<string, string>;
        replaceCurrentRoute(target: string): void;
    } | null;
}

interface AutomationInitialModalController {
    handleAction(actionId: AutomationActionId, element: HTMLElement): void;
}

const clearAutomationInitialModalQuery = (host: AutomationInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Automation initial modal cleanup requires a router');
    }
    router.replaceCurrentRoute(buildRouteWithoutQueryParameters('automation', router.getRouteParameters(), ['modal']));
};

const handleAutomationInitialModal = (host: AutomationInitialModalHost, controller: AutomationInitialModalController, modal: string | null): void => {
    if (modal !== 'add-automation') {
        return;
    }
    controller.handleAction(AUTOMATION_ACTION_OPEN_CREATE_MODAL, host.pageDom.requireHTMLElement('#automation-create-button'));
    clearAutomationInitialModalQuery(host);
};

export { handleAutomationInitialModal };

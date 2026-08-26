/* SoAI - Dashboard page action dispatch controller [frontend/assets/ts/pages/dashboard/controllers/DashboardActionDispatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DASHBOARD_ACTION_IMAGE_UPLOAD, type DashboardActionId } from '@pages/dashboard/actions.ts';
import type { DashboardRuntime } from '@pages/dashboard/adapters/DashboardRuntimeManager.ts';

const dispatchClickAction = (runtime: DashboardRuntime, event: Event, actionCandidate: DashboardActionId, actionElement: HTMLElement): void => {
    if (actionCandidate === DASHBOARD_ACTION_IMAGE_UPLOAD && event.target instanceof HTMLInputElement) {
        return;
    }
    const handler = runtime.actionHandlers[actionCandidate];
    if (!handler) {
        throw new Error(`Dashboard missing action handler for ${actionCandidate}`);
    }
    event.preventDefault();
    handler(actionElement);
};

const dispatchChangeAction = (runtime: DashboardRuntime, event: Event, actionCandidate: DashboardActionId): void => {
    if (actionCandidate !== DASHBOARD_ACTION_IMAGE_UPLOAD || !(event.target instanceof HTMLInputElement)) {
        return;
    }
    runtime.imageCard.handleUpload(event.target);
};

const DashboardActionDispatchController = Object.freeze({
    dispatchChangeAction,
    dispatchClickAction
});

export { DashboardActionDispatchController };

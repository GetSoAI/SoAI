/* SoAI - Automation page preferences actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/preferencesActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';

const handleResetPreferences = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.resetPreferences();
};

export { handleResetPreferences };

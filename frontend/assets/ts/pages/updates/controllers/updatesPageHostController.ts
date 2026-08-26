/* SoAI - Core application update controller host [frontend/assets/ts/pages/updates/controllers/updatesPageHostController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoftwareUpdateAcceptedResponse, SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';
import type { UpdatesControllerSystemSurface } from '@pages/updates/controllers/contracts.ts';
import type { UpdatesSystemControllerHost } from '@pages/updates/controllers/UpdatesSystemControllerContract.ts';

interface UpdatesPageControllerHostDependencies {
    systemSurface: UpdatesControllerSystemSurface;
    checkUpdates(): Promise<SoftwareUpdateCheckResponse>;
    updateSoAI(): Promise<SoftwareUpdateAcceptedResponse>;
    onApplicationInstallStarted(): number;
}

const createUpdatesSystemControllerHost = (dependencies: UpdatesPageControllerHostDependencies): UpdatesSystemControllerHost => ({
    api: {
        checkUpdates: dependencies.checkUpdates,
        updateSoAI: dependencies.updateSoAI
    },
    notify: dependencies.systemSurface.notify,
    setButtonLoading: dependencies.systemSurface.setButtonLoading,
    handleError: dependencies.systemSurface.handleError,
    toggleHidden: dependencies.systemSurface.toggleHidden,
    updateText: dependencies.systemSurface.updateText,
    updateHTML: dependencies.systemSurface.updateHTML,
    updateProperty: dependencies.systemSurface.updateProperty,
    updateCheckerboard: dependencies.systemSurface.updateCheckerboard,
    sanitizeHtml: dependencies.systemSurface.sanitizeHtml,
    sanitizeAttribute: dependencies.systemSurface.sanitizeAttribute,
    sanitizeUrl: dependencies.systemSurface.sanitizeUrl,
    getIconSync: dependencies.systemSurface.getIconSync,
    showOverlay: dependencies.systemSurface.showOverlay,
    resolveInstallButton: dependencies.systemSurface.resolveInstallButton,
    wait: dependencies.systemSurface.wait,
    onInstallStarted: dependencies.onApplicationInstallStarted
});

export { createUpdatesSystemControllerHost };
export type { UpdatesPageControllerHostDependencies };

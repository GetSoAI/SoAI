/* SoAI - Updates page system controller contract [frontend/assets/ts/pages/updates/controllers/UpdatesSystemControllerContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoftwareUpdateAcceptedResponse, SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';
import type { UpdatesControllerSystemSurface } from '@pages/updates/controllers/contracts.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';

type SystemUiRefs = Pick<UpdatesUiRefs, 'statusIcon' | 'statusSpinner' | 'statusHeading' | 'statusDetail' | 'detailsSection' | 'summaryContainer' | 'notesContainer' | 'notesBody'>;

interface UpdatesSystemControllerHost extends UpdatesControllerSystemSurface {
    api: {
        checkUpdates: () => Promise<SoftwareUpdateCheckResponse>;
        updateSoAI: () => Promise<SoftwareUpdateAcceptedResponse>;
    };
    onInstallStarted: () => number;
}

export type { SystemUiRefs, UpdatesSystemControllerHost };

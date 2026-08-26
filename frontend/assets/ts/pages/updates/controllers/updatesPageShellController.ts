/* SoAI - Core application update shell composition [frontend/assets/ts/pages/updates/controllers/updatesPageShellController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyInitialUpdatesNotice } from '@pages/updates/controllers/updatesPageNoticeController.ts';
import { UpdatesSystemController } from '@pages/updates/controllers/UpdatesSystemController.ts';
import type { UpdatesSystemControllerHost } from '@pages/updates/controllers/UpdatesSystemControllerContract.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';

interface UpdatesPageShellDependencies {
    ui: UpdatesUiRefs;
    checkButton: HTMLButtonElement;
    createSystemHost(): UpdatesSystemControllerHost;
    createNoticeHost(): {
        updateText(element: Element, text: string): void;
        toggleHidden(element: Element, hidden: boolean): void;
    };
}

const initializeUpdatesPageShell = (dependencies: UpdatesPageShellDependencies): UpdatesSystemController => {
    applyInitialUpdatesNotice(dependencies.createNoticeHost(), dependencies.ui);
    const controller = new UpdatesSystemController({
        host: dependencies.createSystemHost(),
        ui: {
            statusIcon: dependencies.ui.statusIcon,
            statusSpinner: dependencies.ui.statusSpinner,
            statusHeading: dependencies.ui.statusHeading,
            statusDetail: dependencies.ui.statusDetail,
            detailsSection: dependencies.ui.detailsSection,
            summaryContainer: dependencies.ui.summaryContainer,
            notesContainer: dependencies.ui.notesContainer,
            notesBody: dependencies.ui.notesBody
        }
    });
    controller.initialize(dependencies.checkButton);
    return controller;
};

export { initializeUpdatesPageShell };

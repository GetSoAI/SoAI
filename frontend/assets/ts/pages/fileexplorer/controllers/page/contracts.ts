/* SoAI - File explorer page control layer boundary contracts [frontend/assets/ts/pages/fileexplorer/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { FileExplorerDataController } from '@pages/fileexplorer/controllers/FileExplorerDataController.ts';
import type { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';
import type { FileExplorerPageInteractionController } from '@pages/fileexplorer/controllers/FileExplorerPageInteractionController.ts';
import type { FileExplorerApi, FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { FileExplorerSortState } from '@pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts';

interface FileExplorerPageRuntimeHost {
    api: {
        fileExplorer: FileExplorerApi;
        system: {
            cancelTask: (taskId: string, reason: string) => Promise<TaskCancellationResponse>;
        };
    };
    storage: StorageService;
    pageLifecycle: PageLifecycle;
    pageDom: PageDom;
    feedback: PageFeedback;
    services: PageServices;
    layout: PageLayout;
    modalPresenter: ModalPresenterApi;
    waitForTask: (taskId: string, signal: AbortSignal) => Promise<void>;
}

interface FileExplorerPageRuntime {
    ui: FileExplorerUiRefs;
    dataController: FileExplorerDataController;
    operationsController: FileExplorerOperationsController;
    interactionController: FileExplorerPageInteractionController;
    prepareInitialContent: (signal: AbortSignal | null) => Promise<void>;
    holdInitialReveal: () => void;
    releaseInitialReveal: () => void;
    navigateHome: () => Promise<void>;
    navigatePrevious: () => Promise<void>;
    navigateNext: () => Promise<void>;
    navigateUp: () => Promise<void>;
    navigatePath: (path: string) => Promise<void>;
    applyCurrentSortSelection: () => Promise<void>;
    loadNextPage: () => Promise<void>;
    setModalOpen: (modalOpen: boolean) => void;
    resetSearchOnNavigation: () => void;
    clearDeeplinkHighlight: () => void;
    destroy: () => void;
}

interface FileExplorerRuntimeInitializationOptions {
    initialPath: string;
    highlightPath: string | null;
    searchQuery: string | null;
    previewPath: string | null;
    sortState: FileExplorerSortState;
}

export type { FileExplorerPageRuntime, FileExplorerPageRuntimeHost, FileExplorerRuntimeInitializationOptions };

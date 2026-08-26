/* SoAI - Models page control layer public contracts [frontend/assets/ts/pages/models/controllers/page/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamActionHandle, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { DownloadModalController, EditModelModalManager, ProvidersManager, RenameModelModalManager, VirtualModelsManager } from '@features/models/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ModelsItemDeletionConfig {
    identifier: string;
    confirmTitle: string;
    confirmMessage: string;
    confirmButton: string;
    getStream: () => Promise<StreamActionHandle>;
    gridId: string;
    findCard?: (grid: HTMLElement | null, id: string) => HTMLElement | null;
    pendingClass: string;
    successMessage: string;
}

interface ModelsModalManagerBundle {
    providersManager: ProvidersManager;
    downloadModalManager: DownloadModalController;
    editModelModalManager: EditModelModalManager;
    renameModelModalManager: RenameModelModalManager;
    virtualModelsManager: VirtualModelsManager;
}

interface ModelsItemDeletionHost extends PageDomOwnerHost, PageFeedbackOwnerHost {
    deletingItems: Set<string>;
    streams: StreamHandleTrackerContract;
    renderItems: () => void;
    removeItemById: (id: string) => void;
    cancelLabel: string;
}

export type { ModelsItemDeletionConfig, ModelsItemDeletionHost, ModelsModalManagerBundle };

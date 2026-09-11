/* SoAI - Models page download progress and empty-state coordination [frontend/assets/ts/pages/models/controllers/ModelsDownloadProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { createTaskOperationPanel, type TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import type { TaskOperationEntry } from '@core/tasks/protocols.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import { MODEL_DOWNLOAD_OPERATION_FILTER } from '@features/models/public.ts';
import { requireModelsUi } from '@pages/models/dom.ts';

interface ModelsDownloadProgressControllerDependencies {
    domOwner: PageDomOwnerHost;
    requestCollectionRender: () => void;
}

class ModelsDownloadProgressController {
    readonly #dependencies: ModelsDownloadProgressControllerDependencies;
    #operationPanel: TaskOperationPanel | null = null;
    #progressSection: HTMLElement | null = null;
    #hasActiveDownloads = false;
    #modelDataReady = false;
    #authoritativeModelCount = 0;
    #destroyed = false;

    constructor(dependencies: ModelsDownloadProgressControllerDependencies) {
        this.#dependencies = dependencies;
    }

    initialize(): void {
        this.#releasePanel();
        this.#destroyed = false;
        this.#progressSection = requireModelsUi(this.#dependencies.domOwner).downloadProgress;
        this.#syncProgressVisibility();
        const operationPanel = createTaskOperationPanel({
            container: this.#progressSection,
            filter: MODEL_DOWNLOAD_OPERATION_FILTER,
            onOperationsChanged: (operations) => this.#acceptOperations(operations)
        });
        this.#operationPanel = operationPanel;
        try {
            operationPanel.attach();
        } catch (error) {
            operationPanel.detach();
            this.#operationPanel = null;
            this.#progressSection = null;
            throw error;
        }
    }

    acceptAuthoritativeSnapshot(modelCount: number): void {
        if (this.#destroyed) {
            return;
        }
        this.#modelDataReady = true;
        this.#authoritativeModelCount = modelCount;
        this.#syncProgressVisibility();
    }

    syncAuthoritativeModelCount(modelCount: number): void {
        if (this.#destroyed) {
            return;
        }
        this.#authoritativeModelCount = modelCount;
        this.#syncProgressVisibility();
    }

    shouldShowNormalEmptyState(modelCount: number): boolean {
        return this.#modelDataReady && modelCount === 0 && !this.#hasActiveDownloads;
    }

    destroy(): void {
        this.#destroyed = true;
        this.#releasePanel();
        this.#hasActiveDownloads = false;
        this.#modelDataReady = false;
        this.#authoritativeModelCount = 0;
    }

    #acceptOperations(operations: readonly TaskOperationEntry[]): void {
        if (this.#destroyed) {
            return;
        }
        const hasActiveDownloads = operations.length > 0;
        const presenceChanged = hasActiveDownloads !== this.#hasActiveDownloads;
        this.#hasActiveDownloads = hasActiveDownloads;
        this.#syncProgressVisibility();
        if (presenceChanged) {
            this.#dependencies.requestCollectionRender();
        }
    }

    #syncProgressVisibility(): void {
        const visible = this.#modelDataReady && this.#authoritativeModelCount === 0 && this.#hasActiveDownloads;
        setVisibilityState(this.#progressSection, visible, { ariaHidden: true });
    }

    #releasePanel(): void {
        this.#operationPanel?.detach();
        this.#operationPanel = null;
        setVisibilityState(this.#progressSection, false, { ariaHidden: true });
        this.#progressSection = null;
    }
}

export { ModelsDownloadProgressController };

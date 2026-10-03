/* SoAI - Automation page pane controller [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/paneController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/types.ts';
import { AutomationWindowRunsDeleteController } from '@pages/automation/controllers/windowrunstoolbar/deleteController.ts';
import { resolveAutomationWindowRunsToolbarUi } from '@pages/automation/controllers/windowrunstoolbar/dom.ts';
import { AutomationWindowRunsSelectionManager } from '@pages/automation/controllers/windowrunstoolbar/selectionManager.ts';
import { AutomationWindowRunsToolbarController } from '@pages/automation/controllers/windowrunstoolbar/toolbarController.ts';
import type { AutomationDataService, AutomationOccurrenceResponse } from '@features/automation/public.ts';
import { buildAutomationZoneKeyForZone } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

type AutomationWindowRunsPaneControllerDependencies = {
    dataService: AutomationDataService;
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
    queueRender: () => void;
    run: (operation: string, task: () => Promise<void> | void) => void;
    closeOccurrenceModal: () => void;
};

class AutomationWindowRunsPaneController {
    readonly #dependencies: AutomationWindowRunsPaneControllerDependencies;
    readonly #selection: AutomationWindowRunsSelectionManager;
    readonly #toolbar: AutomationWindowRunsToolbarController;
    readonly #delete: AutomationWindowRunsDeleteController;
    #windowSignature: string | null = null;

    constructor(dependencies: AutomationWindowRunsPaneControllerDependencies) {
        this.#dependencies = dependencies;
        this.#selection = new AutomationWindowRunsSelectionManager({
            queueRender: dependencies.queueRender
        });
        this.#toolbar = new AutomationWindowRunsToolbarController(this.#selection);
        this.#delete = new AutomationWindowRunsDeleteController({
            dataService: dependencies.dataService,
            getState: dependencies.getState,
            refreshData: dependencies.refreshData,
            showNotification: dependencies.showNotification,
            selection: this.#selection,
            onPendingChanged: (pending) => this.#selection.setMutationPending(pending)
        });
    }

    dispose(): void {
        this.#delete.dispose();
        this.#toolbar.dispose();
    }

    isSelectionActive(): boolean {
        return this.#selection.isActive();
    }

    selectedKeys(): ReadonlySet<string> {
        return this.#selection.keys();
    }

    reconcileSelection(zones: readonly AutomationOccurrenceResponse[], windowSignature: string): void {
        if (this.#windowSignature !== windowSignature) {
            this.#delete.cancelPending();
            this.#windowSignature = windowSignature;
            this.#selection.deactivate({ queueRender: false });
        }
        this.#selection.reconcile(new Set(zones.map(buildAutomationZoneKeyForZone)));
    }

    bindUi(windowRunsRoot: HTMLElement, totalRunsCount: number): void {
        this.#toolbar.bindUi(resolveAutomationWindowRunsToolbarUi(windowRunsRoot));
        this.#toolbar.updateTotalRunsCount(totalRunsCount);
    }

    enterSelectMode(): void {
        const state = this.#dependencies.getState();
        if (state.selectedZoneKey) {
            this.#dependencies.setState({ ...state, selectedZoneKey: null });
        }
        this.#dependencies.closeOccurrenceModal();
        this.#toolbar.enterSelectMode();
    }

    exitSelectMode(): void {
        this.#toolbar.exitSelectMode();
    }

    toggleOccurrenceSelected(zoneKey: string): void {
        this.#toolbar.handleOccurrenceClick(zoneKey);
    }

    batchDelete(): void {
        this.#dependencies.run('automation:windowRuns:batchDelete', async () => {
            await this.#delete.deleteSelected();
        });
    }

    deleteOne(zoneKey: string): void {
        this.#dependencies.run('automation:windowRuns:deleteOne', async () => {
            const deleted = await this.#delete.deleteOne(zoneKey);
            const state = this.#dependencies.getState();
            if (deleted && state.selectedZoneKey === zoneKey) {
                this.#dependencies.closeOccurrenceModal();
            }
        });
    }
}

export { AutomationWindowRunsPaneController };

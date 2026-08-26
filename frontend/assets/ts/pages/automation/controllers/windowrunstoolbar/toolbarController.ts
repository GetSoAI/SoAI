/* SoAI - Automation page toolbar controller [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/toolbarController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { AutomationWindowRunsSelectionManager } from '@pages/automation/controllers/windowrunstoolbar/selectionManager.ts';
import type { AutomationWindowRunsToolbarUiRefs } from '@pages/automation/controllers/windowrunstoolbar/types.ts';

class AutomationWindowRunsToolbarController {
    #selection: AutomationWindowRunsSelectionManager;
    #ui: AutomationWindowRunsToolbarUiRefs | null = null;

    constructor(selection: AutomationWindowRunsSelectionManager) {
        this.#selection = selection;
    }

    bindUi(refs: AutomationWindowRunsToolbarUiRefs): void {
        this.#ui = refs;
        this.#selection.bindUi(refs);
    }

    dispose(): void {
        this.#ui = null;
    }

    enterSelectMode(): void {
        if (this.#selection.isActive()) {
            return;
        }
        this.#selection.activate();
    }

    exitSelectMode(): void {
        if (!this.#selection.isActive()) {
            return;
        }
        this.#selection.deactivate();
    }

    handleOccurrenceClick(zoneKey: string): void {
        this.#selection.toggleOccurrence(zoneKey);
    }

    updateTotalRunsCount(count: number): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        ui.totalRunsLabel.textContent = i18n.t('automation.pane.windowRuns.toolbar.totalRuns', { count });
        this.#selection.setTotalRunsCount(count);
    }
}

export { AutomationWindowRunsToolbarController };

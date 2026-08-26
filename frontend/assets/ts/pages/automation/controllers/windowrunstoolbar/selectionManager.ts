/* SoAI - Automation page selection manager [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/selectionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { i18n } from '@core/i18n/index.ts';
import { SelectionState } from '@core/selection/state.ts';
import { syncSelectionActionVisibility, syncSelectionToolbarVisibility } from '@core/selection/toolbarVisibility.ts';
import { queryAutomationWindowRunItems } from '@pages/automation/controllers/windowrunstoolbar/dom.ts';
import type { AutomationWindowRunsToolbarUiRefs } from '@pages/automation/controllers/windowrunstoolbar/types.ts';

type SelectionManagerDependencies = {
    queueRender: () => void;
};

type SelectionModeOptions = {
    queueRender?: boolean | undefined;
};

class AutomationWindowRunsSelectionManager {
    readonly #dependencies: SelectionManagerDependencies;
    #ui: AutomationWindowRunsToolbarUiRefs | null = null;
    #totalRunsCount = 0;
    readonly #selection = new SelectionState();

    constructor(dependencies: SelectionManagerDependencies) {
        this.#dependencies = dependencies;
    }

    bindUi(refs: AutomationWindowRunsToolbarUiRefs): void {
        this.#ui = refs;
        this.#syncToolbarUi();
        this.#syncRunItemSelectionClasses();
    }

    isActive(): boolean {
        return this.#selection.isActive();
    }

    has(zoneKey: string): boolean {
        return this.#selection.has(zoneKey);
    }

    keys(): ReadonlySet<string> {
        return this.#selection.keys();
    }

    list(): readonly string[] {
        return this.#selection.list();
    }

    size(): number {
        return this.#selection.size();
    }

    setTotalRunsCount(count: number): void {
        this.#totalRunsCount = Number.isInteger(count) && count > 0 ? count : 0;
        if (this.#totalRunsCount < 2 && this.#selection.isActive()) {
            this.#selection.clear();
            this.#selection.setActive(false);
        }
        this.#syncToolbarUi();
        this.#syncRunItemSelectionClasses();
    }

    activate(options: SelectionModeOptions = {}): void {
        if (this.#totalRunsCount < 2) {
            return;
        }
        if (this.#selection.isActive()) {
            return;
        }
        this.#selection.clear();
        this.#selection.setActive(true);
        this.#syncToolbarUi();
        this.#syncRunItemSelectionClasses();
        if (options.queueRender !== false) {
            this.#dependencies.queueRender();
        }
    }

    deactivate(options: SelectionModeOptions = {}): void {
        if (!this.#selection.isActive()) {
            return;
        }
        this.#selection.clear();
        this.#selection.setActive(false);
        this.#syncToolbarUi();
        this.#syncRunItemSelectionClasses();
        if (options.queueRender !== false) {
            this.#dependencies.queueRender();
        }
    }

    toggleOccurrence(zoneKey: string): void {
        if (!this.#selection.isActive()) {
            return;
        }
        const key = zoneKey.trim();
        if (!key) {
            throw new Error('Automation window run selection requires a zone key');
        }
        this.#selection.toggle(key);
        this.#syncToolbarUi();
        this.#syncRunItemSelectionForKey(key);
    }

    #syncToolbarUi(): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        const active = this.#selection.isActive();
        syncSelectionToolbarVisibility(
            {
                modeTarget: ui.runsList,
                toggleButton: ui.selectButton,
                batchActionsContainer: ui.batchActionsContainer,
                totalElements: [ui.totalRunsIcon, ui.totalRunsLabel],
                selectedElements: [ui.selectedCountIcon, ui.selectedCountLabel]
            },
            active
        );
        ui.selectButton.classList.toggle(CSS_CLASSES.HIDDEN, active || this.#totalRunsCount < 2);

        const count = this.#selection.size();
        ui.selectedCountLabel.textContent = i18n.t('automation.pane.windowRuns.toolbar.selectedCount', { count });
        const hasSelection = count > 0;
        ui.batchDeleteButton.disabled = !hasSelection;
        syncSelectionActionVisibility(ui.batchDeleteButton, hasSelection);
        if (!active) {
            ui.batchDeleteButton.disabled = true;
            syncSelectionActionVisibility(ui.batchDeleteButton, false);
        }
    }

    #syncRunItemSelectionClasses(): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        for (const element of queryAutomationWindowRunItems(ui.runsList)) {
            const zoneKey = (element.dataset['zoneKey'] ?? '').trim();
            if (!zoneKey) {
                continue;
            }
            element.classList.toggle('is-batch-selected', this.#selection.isActive() && this.#selection.has(zoneKey));
        }
    }

    #syncRunItemSelectionForKey(zoneKey: string): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        for (const element of queryAutomationWindowRunItems(ui.runsList)) {
            const elementKey = (element.dataset['zoneKey'] ?? '').trim();
            if (elementKey !== zoneKey) {
                continue;
            }
            element.classList.toggle('is-batch-selected', this.#selection.isActive() && this.#selection.has(zoneKey));
        }
    }
}

export { AutomationWindowRunsSelectionManager };
export type { SelectionManagerDependencies };

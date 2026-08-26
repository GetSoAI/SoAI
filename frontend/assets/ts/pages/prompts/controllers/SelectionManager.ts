/* SoAI - Prompts page selection manager [frontend/assets/ts/pages/prompts/controllers/SelectionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { SelectionState } from '@core/selection/state.ts';

interface SelectionUiRefs {
    grid: HTMLElement;
    listTable: HTMLElement;
    listSelectAllCheckbox: HTMLInputElement;
    toggleSelectionButton: HTMLElement;
    createPromptButton: HTMLElement;

    selectedPromptsCard: HTMLElement;
    selectedPromptsValue: HTMLElement;

    selectAllButton: HTMLElement;
    deselectAllButton: HTMLElement;
    duplicateSelectedButton: HTMLElement;
    duplicateSelectedLabel: HTMLElement;
    downloadSelectedButton: HTMLElement;
    downloadSelectedLabel: HTMLElement;
    deleteSelectedButton: HTMLButtonElement;
    deleteSelectedLabel: HTMLElement;
}

interface SelectionDependencies {
    getFilteredPromptIds: () => readonly string[];
    renderItems: () => void;
    refreshPromptCards: (ids?: readonly string[]) => void;
    updateStats: () => void;
    toggleClassName: (element: Element, className: string, force: boolean) => void;
    updateAttribute: (element: Element, name: string, value: string) => void;
    updateText: (element: Element, text: string) => void;
    addClassName: (element: Element, className: string) => void;
    removeClassName: (element: Element, className: string) => void;
    setElementVisibility: (element: Element | undefined, visible: boolean) => void;
}

class SelectionManager {
    #dependencies: SelectionDependencies;
    #ui: SelectionUiRefs | null;
    readonly #selection: SelectionState;

    constructor(dependencies: SelectionDependencies) {
        this.#dependencies = dependencies;
        this.#ui = null;
        this.#selection = new SelectionState();
    }

    bindUi(ui: SelectionUiRefs): void {
        this.#ui = ui;
    }

    isActive(): boolean {
        return this.#selection.isActive();
    }

    has(promptId: string): boolean {
        return this.#selection.has(promptId);
    }

    list(): readonly string[] {
        return this.#selection.list();
    }

    size(): number {
        return this.#selection.size();
    }

    clear(): void {
        this.#selection.clear();
    }

    toggleMode(): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Selection UI is not bound');
        }
        const active = !this.#selection.isActive();
        this.#selection.setActive(active);
        this.#dependencies.toggleClassName(ui.listTable, 'selection-mode', active);
        if (active) {
            this.#dependencies.addClassName(ui.toggleSelectionButton, 'is-active');
            this.#dependencies.setElementVisibility(ui.createPromptButton, false);
            this.#setBatchActionsVisible(true);
            this.#dependencies.addClassName(ui.grid, 'selection-mode');
            this.#dependencies.toggleClassName(ui.selectedPromptsCard, 'u-hidden', false);
        } else {
            this.#dependencies.removeClassName(ui.toggleSelectionButton, 'is-active');
            this.#dependencies.setElementVisibility(ui.createPromptButton, true);
            this.#setBatchActionsVisible(false);
            this.#dependencies.removeClassName(ui.grid, 'selection-mode');
            this.#dependencies.toggleClassName(ui.selectedPromptsCard, 'u-hidden', true);
            this.clear();
        }
        this.refreshUI();
        this.#dependencies.renderItems();
        this.#dependencies.refreshPromptCards();
    }

    selectAll(): void {
        const ids = this.#dependencies.getFilteredPromptIds();
        this.#selection.addMany(ids);
        this.#dependencies.renderItems();
        this.#dependencies.refreshPromptCards(ids);
        this.refreshUI();
    }

    deselectAll(): void {
        this.clear();
        if (this.#selection.isActive()) {
            this.toggleMode();
            return;
        }
        this.#dependencies.renderItems();
        this.#dependencies.refreshPromptCards();
        this.refreshUI();
    }

    togglePrompt(promptId: string): void {
        this.#selection.toggle(promptId);
        if (this.#selection.size() === 0) {
            this.toggleMode();
            return;
        }
        this.#dependencies.refreshPromptCards([promptId]);
        this.refreshUI();
    }

    refreshUI(): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        const count = this.#selection.size();
        const hasSelection = count > 0;
        const disabled = !hasSelection;
        const filteredIds = this.#dependencies.getFilteredPromptIds();
        const selectedFilteredCount = filteredIds.filter((promptId) => this.#selection.has(promptId)).length;
        const canSelectAll = this.#selection.isActive() && filteredIds.length > 0 && selectedFilteredCount < filteredIds.length;
        const canDeselectAll = this.#selection.isActive() && hasSelection;

        ui.listSelectAllCheckbox.checked = filteredIds.length > 0 && selectedFilteredCount === filteredIds.length;
        ui.listSelectAllCheckbox.indeterminate = selectedFilteredCount > 0 && selectedFilteredCount < filteredIds.length;

        this.#dependencies.toggleClassName(ui.selectAllButton, 'u-hidden', !canSelectAll);
        this.#dependencies.updateAttribute(ui.selectAllButton, 'aria-hidden', canSelectAll ? 'false' : 'true');

        this.#dependencies.toggleClassName(ui.deselectAllButton, 'u-hidden', !canDeselectAll);
        this.#dependencies.updateAttribute(ui.deselectAllButton, 'aria-hidden', canDeselectAll ? 'false' : 'true');

        this.#dependencies.toggleClassName(ui.deleteSelectedButton, 'u-hidden', disabled);
        this.#dependencies.updateAttribute(ui.deleteSelectedButton, 'aria-hidden', disabled ? 'true' : 'false');
        ui.deleteSelectedButton.disabled = disabled;

        this.#dependencies.toggleClassName(ui.duplicateSelectedButton, 'u-hidden', disabled);
        this.#dependencies.updateAttribute(ui.duplicateSelectedButton, 'aria-hidden', disabled ? 'true' : 'false');

        this.#dependencies.toggleClassName(ui.downloadSelectedButton, 'u-hidden', disabled);
        this.#dependencies.updateAttribute(ui.downloadSelectedButton, 'aria-hidden', disabled ? 'true' : 'false');

        this.#dependencies.updateText(ui.duplicateSelectedLabel, count > 1 ? i18n.t('prompts.actions.duplicateCount', { count }) : i18n.t('prompts.actions.duplicate'));
        this.#dependencies.updateText(ui.downloadSelectedLabel, count > 1 ? i18n.t('prompts.actions.downloadCount', { count }) : i18n.t('prompts.actions.download'));
        this.#dependencies.updateText(ui.deleteSelectedLabel, count > 1 ? i18n.t('prompts.actions.deleteCount', { count }) : i18n.t('prompts.actions.delete'));

        this.#dependencies.updateText(ui.selectedPromptsValue, String(count));
        this.#dependencies.updateStats();
    }

    #setBatchActionsVisible(visible: boolean): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        const controls: readonly HTMLElement[] = [ui.selectAllButton, ui.deselectAllButton, ui.duplicateSelectedButton, ui.downloadSelectedButton, ui.deleteSelectedButton];
        controls.forEach((element) => {
            this.#dependencies.toggleClassName(element, 'u-hidden', !visible);
            this.#dependencies.updateAttribute(element, 'aria-hidden', visible ? 'false' : 'true');
        });
    }
}

export { SelectionManager };
export type { SelectionDependencies, SelectionUiRefs };

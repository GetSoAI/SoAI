/* SoAI - Prompts page DOM contracts [frontend/assets/ts/pages/prompts/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowSelect } from '@core/dom/narrowElement.ts';
import { requireInputElement } from '@core/dom/typedElements.ts';
import { requireHeaderStatCard } from '@core/routing/pages/basepagelayout/headerStats.ts';
import { promptsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import type { PromptsUiRefs } from '@pages/prompts/types.ts';

const GRID_ID = promptsPageConfig.grid.gridId;

export const resolvePromptsSaveButtons = (root: HTMLElement): readonly HTMLButtonElement[] => {
    const buttons: HTMLButtonElement[] = [];
    for (const candidate of dom.resolveAll('button[data-action="prompts.cardSaveEdit"]', root)) {
        if (candidate instanceof HTMLButtonElement) {
            buttons.push(candidate);
        }
    }
    return buttons;
};

export const requirePromptsUi = (dependencies: { requireHTMLElement: (selector: string, context?: Element) => HTMLElement; optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null }): PromptsUiRefs => {
    const root = dependencies.requireHTMLElement('[data-section="prompts"]');
    const grid = dependencies.requireHTMLElement(`#${GRID_ID}`, root);
    const listBody = dependencies.requireHTMLElement('#prompts-list-body', root);
    const listTable = dependencies.requireHTMLElement('.prompts-list-table', root);
    const listSelectAllCheckbox = requireInputElement(dependencies, '#prompts-list-select-all', 'Prompts list select-all checkbox', root);
    const viewModeToggleButton = narrowButton(dependencies.requireHTMLElement('#prompts-view-mode-toggle', root), 'Prompts view mode toggle');

    const sortSelect = narrowSelect(dependencies.requireHTMLElement('#prompts-sort', root), 'Sort select');

    const createPromptButton = narrowButton(dependencies.requireHTMLElement('#create-prompt', root), 'Create prompt button');
    const toggleSelectionButton = narrowButton(dependencies.requireHTMLElement('#toggle-selection-mode', root), 'Toggle selection mode button');
    const selectAllButton = narrowButton(dependencies.requireHTMLElement('#select-all', root), 'Select all button');
    const deselectAllButton = narrowButton(dependencies.requireHTMLElement('#deselect-all', root), 'Deselect all button');
    const duplicateSelectedButton = narrowButton(dependencies.requireHTMLElement('#duplicate-selected', root), 'Duplicate selected button');
    const downloadSelectedButton = narrowButton(dependencies.requireHTMLElement('#download-selected', root), 'Download selected button');
    const deleteSelectedButton = narrowButton(dependencies.requireHTMLElement('#delete-selected', root), 'Delete selected');
    const duplicateSelectedLabel = dependencies.requireHTMLElement('.prompts-batch-action-label', duplicateSelectedButton);
    const downloadSelectedLabel = dependencies.requireHTMLElement('.prompts-batch-action-label', downloadSelectedButton);
    const deleteSelectedLabel = dependencies.requireHTMLElement('.prompts-batch-action-label', deleteSelectedButton);

    const totalPromptsValue = dependencies.requireHTMLElement('#total-prompts', root);
    const specialPromptsValue = dependencies.requireHTMLElement('#special-prompts', root);
    const totalCharactersValue = dependencies.requireHTMLElement('#total-characters', root);
    const lastCreatedValue = dependencies.requireHTMLElement('#last-created', root);
    const lastModifiedValue = dependencies.requireHTMLElement('#last-modified', root);

    const selectedPromptsValue = dependencies.requireHTMLElement('#selected-prompts', root);
    const selectedPromptsCard = requireHeaderStatCard(selectedPromptsValue, 'Selected prompts');

    return {
        root,
        grid,
        listBody,
        listTable,
        listSelectAllCheckbox,
        viewModeToggleButton,
        sortSelect,
        createPromptButton,
        toggleSelectionButton,
        selectAllButton,
        deselectAllButton,
        duplicateSelectedButton,
        duplicateSelectedLabel,
        downloadSelectedButton,
        downloadSelectedLabel,
        deleteSelectedButton,
        deleteSelectedLabel,
        totalPromptsValue,
        specialPromptsValue,
        totalCharactersValue,
        lastCreatedValue,
        lastModifiedValue,
        selectedPromptsValue,
        selectedPromptsCard
    };
};

export const optionalPromptsRoot = (dependencies: { optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null }): HTMLElement | null => dependencies.optionalHTMLElement('[data-section="prompts"]');

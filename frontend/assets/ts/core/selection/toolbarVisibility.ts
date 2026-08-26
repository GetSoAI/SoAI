/* SoAI - Shared multi-select toolbar visibility updates [frontend/assets/ts/core/selection/toolbarVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';

interface SelectionToolbarVisibilityRefs {
    modeTarget: HTMLElement;
    toggleButton: HTMLElement;
    batchActionsContainer: HTMLElement;
    totalElements: readonly HTMLElement[];
    selectedElements: readonly HTMLElement[];
}

const syncSelectionToolbarVisibility = (refs: SelectionToolbarVisibilityRefs, active: boolean): void => {
    refs.toggleButton.classList.toggle('is-active', active);
    refs.modeTarget.classList.toggle('selection-mode', active);
    refs.toggleButton.classList.toggle(CSS_CLASSES.HIDDEN, active);
    refs.batchActionsContainer.classList.toggle(CSS_CLASSES.HIDDEN, !active);
    refs.totalElements.forEach((element) => {
        element.classList.toggle(CSS_CLASSES.HIDDEN, active);
    });
    refs.selectedElements.forEach((element) => {
        element.classList.toggle(CSS_CLASSES.HIDDEN, !active);
    });
};

const syncSelectionActionVisibility = (element: HTMLElement, visible: boolean): void => {
    element.classList.toggle(CSS_CLASSES.HIDDEN, !visible);
};

export { syncSelectionActionVisibility, syncSelectionToolbarVisibility };
export type { SelectionToolbarVisibilityRefs };

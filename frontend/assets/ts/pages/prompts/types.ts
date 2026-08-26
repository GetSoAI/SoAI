/* SoAI - Prompts page public contracts [frontend/assets/ts/pages/prompts/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export interface PromptsUiRefs {
    root: HTMLElement;
    grid: HTMLElement;
    listBody: HTMLElement;
    listTable: HTMLElement;
    listSelectAllCheckbox: HTMLInputElement;
    viewModeToggleButton: HTMLButtonElement;
    sortSelect: HTMLSelectElement;
    createPromptButton: HTMLButtonElement;
    toggleSelectionButton: HTMLButtonElement;
    selectAllButton: HTMLButtonElement;
    deselectAllButton: HTMLButtonElement;
    duplicateSelectedButton: HTMLButtonElement;
    duplicateSelectedLabel: HTMLElement;
    downloadSelectedButton: HTMLButtonElement;
    downloadSelectedLabel: HTMLElement;
    deleteSelectedButton: HTMLButtonElement;
    deleteSelectedLabel: HTMLElement;
    totalPromptsValue: HTMLElement;
    specialPromptsValue: HTMLElement;
    totalCharactersValue: HTMLElement;
    lastCreatedValue: HTMLElement;
    lastModifiedValue: HTMLElement;
    selectedPromptsValue: HTMLElement;
    selectedPromptsCard: HTMLElement;
}

export interface SyntaxHighlighterInterface {
    detectLanguage(content: string): string;
    highlight(content: string, language: string): DocumentFragment | Node | string;
}

/* SoAI - File Explorer header command state and labels [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerCommandsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { BUTTON_TEXT_SELECTOR, beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { FileExplorerSelectionView } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';
import type { FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';

type FileExplorerTransferMode = 'copy' | 'move';

interface FileExplorerCommandsControllerDependencies {
    ui: FileExplorerUiRefs;
    onSelectionModeChanged: (inSelectionMode: boolean) => void;
}

const EMPTY_SELECTION_VIEW: FileExplorerSelectionView = {
    selectionCount: 0,
    entryCount: 0,
    isModeActive: false,
    allSelected: false,
    canOfferMode: false,
    canSelectAll: false,
    canDeselectAll: false,
    canInvert: false
};

const labelForCount = (singleLabel: string, batchLabel: string, count: number): string => (count <= 1 ? singleLabel : batchLabel);

const setCommandVisible = (button: HTMLButtonElement, visible: boolean): void => {
    button.classList.toggle('u-hidden', !visible);
};

const setCommandLabel = (button: HTMLButtonElement, label: string): void => {
    const textElement = dom.resolve(BUTTON_TEXT_SELECTOR, button);
    if (!(textElement instanceof HTMLElement)) {
        throw new Error('File Explorer command button is missing its label element');
    }
    textElement.textContent = label;
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
};

class FileExplorerCommandsController {
    readonly #ui: FileExplorerUiRefs;
    readonly #onSelectionModeChanged: (inSelectionMode: boolean) => void;
    #mode: FileExplorerTransferMode | null = null;
    #sources: readonly string[] = [];
    #view: FileExplorerSelectionView = EMPTY_SELECTION_VIEW;
    #modalOpen = false;
    #downloadBusy = false;
    #clearDownloadLoading: (() => void) | null = null;

    constructor(dependencies: FileExplorerCommandsControllerDependencies) {
        this.#ui = dependencies.ui;
        this.#onSelectionModeChanged = dependencies.onSelectionModeChanged;
        this.#render();
    }

    destroy(): void {
        this.#clearDownloadLoading?.();
        this.#clearDownloadLoading = null;
        this.#downloadBusy = false;
        this.#view = EMPTY_SELECTION_VIEW;
        this.exitTransferMode();
    }

    beginSelectionDownload(): () => void {
        if (this.#downloadBusy) {
            throw new Error('File Explorer selection download is already active');
        }
        const clearLoading = beginLoadingButtonWithClear(this.#ui.selectionDownloadButton);
        this.#clearDownloadLoading = clearLoading;
        this.#downloadBusy = true;
        this.#render();
        let active = true;
        return (): void => {
            if (!active) return;
            active = false;
            if (this.#clearDownloadLoading !== clearLoading) return;
            this.#clearDownloadLoading = null;
            clearLoading();
            this.#downloadBusy = false;
            this.#render();
        };
    }

    applySelectionView(view: FileExplorerSelectionView): void {
        this.#view = view;
        this.#render();
    }

    setModalOpen(modalOpen: boolean): void {
        this.#modalOpen = modalOpen;
        this.#render();
    }

    enterCopyMode(sources: readonly string[]): void {
        this.#enterTransferMode('copy', sources);
    }

    enterMoveMode(sources: readonly string[]): void {
        this.#enterTransferMode('move', sources);
    }

    exitTransferMode(): void {
        this.#mode = null;
        this.#sources = [];
        this.#render();
    }

    get transferMode(): FileExplorerTransferMode | null {
        return this.#mode;
    }

    get transferSources(): readonly string[] {
        return this.#sources;
    }

    #enterTransferMode(mode: FileExplorerTransferMode, sources: readonly string[]): void {
        this.#mode = mode;
        this.#sources = sources.map((value) => toVirtualPath(value));
        this.#render();
    }

    #render(): void {
        const view = this.#view;
        const inTransferMode = this.#mode !== null;
        const isSelectionMode = view.isModeActive && !inTransferMode;
        this.#renderSelectionCommands(view, isSelectionMode);
        this.#renderTransferCommands();
        setCommandVisible(this.#ui.toggleSelectionModeButton, !inTransferMode && view.canOfferMode);
        this.#ui.toggleSelectionModeButton.classList.toggle('is-active', isSelectionMode);
        this.#ui.toggleSelectionModeButton.setAttribute('aria-pressed', isSelectionMode ? 'true' : 'false');
        setCommandLabel(this.#ui.toggleSelectionModeButton, isSelectionMode ? i18n.t('common.cancel') : i18n.t('fileExplorer.actions.selectionToggleLabel'));
        this.#ui.sortShell.classList.toggle('u-hidden', isSelectionMode || this.#ui.root.dataset['viewMode'] !== 'icons');
        setCommandVisible(this.#ui.viewModeToggleButton, !isSelectionMode && !inTransferMode);
        this.#ui.newEntryShell.classList.toggle('u-hidden', isSelectionMode || inTransferMode);
        this.#onSelectionModeChanged(isSelectionMode);
    }

    #renderSelectionCommands(view: FileExplorerSelectionView, isSelectionMode: boolean): void {
        const selectionCount = view.selectionCount;
        const scopeVisible = isSelectionMode && !this.#modalOpen;
        const operationsVisible = isSelectionMode && selectionCount > 0;
        setCommandVisible(this.#ui.selectionSelectAllButton, scopeVisible && view.canSelectAll);
        setCommandVisible(this.#ui.selectionDeselectAllButton, scopeVisible && view.canDeselectAll);
        setCommandVisible(this.#ui.selectionInverseButton, scopeVisible && view.canInvert);
        setCommandVisible(this.#ui.selectionMetadataButton, operationsVisible);
        setCommandVisible(this.#ui.selectionSoaiLinkButton, operationsVisible);
        setCommandVisible(this.#ui.selectionRenameButton, operationsVisible && selectionCount === 1);
        setCommandVisible(this.#ui.selectionCopyButton, operationsVisible);
        setCommandVisible(this.#ui.selectionMoveButton, operationsVisible);
        setCommandVisible(this.#ui.selectionDeleteButton, operationsVisible);
        setCommandVisible(this.#ui.selectionDownloadButton, operationsVisible);
        this.#ui.selectionDownloadButton.disabled = this.#downloadBusy;
        setCommandLabel(this.#ui.selectionMetadataButton, labelForCount(i18n.t('fileExplorer.actionBar.metadata.single'), i18n.t('fileExplorer.actionBar.metadata.batch', { count: selectionCount }), selectionCount));
        setCommandLabel(this.#ui.selectionSoaiLinkButton, labelForCount(i18n.t('fileExplorer.actionBar.use.single'), i18n.t('fileExplorer.actionBar.use.batch', { count: selectionCount }), selectionCount));
        setCommandLabel(this.#ui.selectionCopyButton, labelForCount(i18n.t('fileExplorer.actionBar.copy.single'), i18n.t('fileExplorer.actionBar.copy.batch', { count: selectionCount }), selectionCount));
        setCommandLabel(this.#ui.selectionMoveButton, labelForCount(i18n.t('fileExplorer.actionBar.move.single'), i18n.t('fileExplorer.actionBar.move.batch', { count: selectionCount }), selectionCount));
        setCommandLabel(this.#ui.selectionDeleteButton, labelForCount(i18n.t('fileExplorer.actionBar.delete.single'), i18n.t('fileExplorer.actionBar.delete.batch', { count: selectionCount }), selectionCount));
        setCommandLabel(this.#ui.selectionDownloadButton, labelForCount(i18n.t('fileExplorer.actionBar.download.single'), i18n.t('fileExplorer.actionBar.download.batch', { count: selectionCount }), selectionCount));
    }

    #renderTransferCommands(): void {
        const mode = this.#mode;
        const count = this.#sources.length;
        setCommandVisible(this.#ui.copyHereButton, mode === 'copy');
        setCommandVisible(this.#ui.moveHereButton, mode === 'move');
        setCommandVisible(this.#ui.transferCancelButton, mode !== null);
        setCommandLabel(this.#ui.copyHereButton, labelForCount(i18n.t('fileExplorer.actionBar.copyHere.single'), i18n.t('fileExplorer.actionBar.copyHere.batch', { count }), count));
        setCommandLabel(this.#ui.moveHereButton, labelForCount(i18n.t('fileExplorer.actionBar.moveHere.single'), i18n.t('fileExplorer.actionBar.moveHere.batch', { count }), count));
    }
}

export { FileExplorerCommandsController };
export type { FileExplorerTransferMode };

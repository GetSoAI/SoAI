/* SoAI - File explorer page control layer selection interaction controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerSelectionInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { FILE_EXPLORER_ACTION_SELECTION_COPY, FILE_EXPLORER_ACTION_SELECTION_DELETE, FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL, FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD, FILE_EXPLORER_ACTION_SELECTION_INVERSE, FILE_EXPLORER_ACTION_SELECTION_METADATA, FILE_EXPLORER_ACTION_SELECTION_MOVE, FILE_EXPLORER_ACTION_SELECTION_RENAME, FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL, FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK, FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE } from '@features/fileexplorer/public.ts';
import type { FileExplorerCommandsController } from '@pages/fileexplorer/controllers/FileExplorerCommandsController.ts';
import type { FileExplorerBatchController } from '@pages/fileexplorer/controllers/FileExplorerBatchController.ts';
import type { FileExplorerDataController } from '@pages/fileexplorer/controllers/FileExplorerDataController.ts';
import type { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';
import { FileExplorerSelectionActionsController } from '@pages/fileexplorer/controllers/FileExplorerSelectionActionsController.ts';
import type { FileExplorerTaskProgressController } from '@pages/fileexplorer/controllers/FileExplorerTaskProgressController.ts';
import type { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';

interface FileExplorerSelectionInteractionHost {
    showNotification: (message: string, type: NotificationType) => void;
    requireHTMLElement: (selector: string, context?: HTMLElement) => HTMLElement;
    modalPresenter: ModalPresenterApi;
}

class FileExplorerSelectionInteractionController {
    readonly #host: FileExplorerSelectionInteractionHost;
    readonly #selection: FileExplorerSelectionModel;
    readonly #commands: FileExplorerCommandsController;
    readonly #selectionActions: FileExplorerSelectionActionsController;

    constructor(dependencies: { host: FileExplorerSelectionInteractionHost; data: FileExplorerDataController; selection: FileExplorerSelectionModel; operations: FileExplorerOperationsController; batch: FileExplorerBatchController; commands: FileExplorerCommandsController; taskProgress: FileExplorerTaskProgressController }) {
        this.#host = dependencies.host;
        this.#selection = dependencies.selection;
        this.#commands = dependencies.commands;
        this.#selectionActions = new FileExplorerSelectionActionsController(dependencies);
    }

    dispose(): void {
        this.#selectionActions.dispose();
    }

    async handleClick(action: string): Promise<boolean> {
        if (action === FILE_EXPLORER_ACTION_SELECTION_METADATA) {
            await this.#selectionActions.showMetadataForSelection();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL) {
            this.#selection.exitMode();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE) {
            this.#selection.toggleMode();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL) {
            this.#selection.selectAll();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_INVERSE) {
            this.#selection.invert();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_RENAME) {
            await this.#selectionActions.renameSelection();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK) {
            await this.#selectionActions.copySoaiLinkForSelection();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_DELETE) {
            await this.#selectionActions.deleteSelection();
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_COPY) {
            const sources = this.#requireSelection();
            if (sources) {
                this.#commands.enterCopyMode(sources);
            }
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_MOVE) {
            const sources = this.#requireSelection();
            if (sources) {
                this.#commands.enterMoveMode(sources);
            }
            return true;
        }
        if (action === FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD) {
            await this.#selectionActions.downloadSelection();
            return true;
        }
        return false;
    }

    #requireSelection(): readonly string[] | null {
        const sources = this.#selection.getSelectedPaths();
        if (sources.length > 0) {
            return sources;
        }
        this.#host.showNotification(i18n.t('fileExplorer.errors.selectionRequired'), 'error');
        return null;
    }
}

export { FileExplorerSelectionInteractionController };

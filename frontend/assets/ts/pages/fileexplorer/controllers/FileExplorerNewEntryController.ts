/* SoAI - File Explorer New menu execution [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerNewEntryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { joinVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isFileExplorerNewEntryValue, type FileExplorerNewEntryValue } from '@pages/fileexplorer/contracts/contracts.ts';
import type { FileExplorerContentPreviewModalController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewModalController.ts';
import { filenameFromPath } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import type { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';

interface FileExplorerNewEntryControllerDependencies {
    contentPreviewModal: FileExplorerContentPreviewModalController;
    operations: FileExplorerOperationsController;
    getCurrentPath: () => string;
    isDisposed: () => boolean;
}

class FileExplorerNewEntryController {
    readonly #contentPreviewModal: FileExplorerContentPreviewModalController;
    readonly #operations: FileExplorerOperationsController;
    readonly #getCurrentPath: () => string;
    readonly #isDisposed: () => boolean;

    constructor(dependencies: FileExplorerNewEntryControllerDependencies) {
        this.#contentPreviewModal = dependencies.contentPreviewModal;
        this.#operations = dependencies.operations;
        this.#getCurrentPath = dependencies.getCurrentPath;
        this.#isDisposed = dependencies.isDisposed;
    }

    async run(selectElement: HTMLSelectElement): Promise<void> {
        const requestedValue = selectElement.value;
        selectElement.selectedIndex = 0;
        if (requestedValue === '') {
            return;
        }
        if (!isFileExplorerNewEntryValue(requestedValue)) {
            throw new Error('File Explorer New menu received an invalid option');
        }
        await this.#execute(requestedValue);
    }

    async #execute(value: FileExplorerNewEntryValue): Promise<void> {
        if (value === 'uploadFiles' || value === 'uploadFolder') {
            this.#operations.openUploadPicker({ directory: value === 'uploadFolder' });
            return;
        }
        if (value === 'file') {
            this.#contentPreviewModal.showNewFile(this.#buildDestinationPath(i18n.t('fileExplorer.defaultNewFileName')));
            return;
        }
        await this.#createFolder();
    }

    async #createFolder(): Promise<void> {
        const name = await requireDialogsService().showPrompt({
            title: i18n.t('fileExplorer.modals.createFolder.title'),
            message: i18n.t('fileExplorer.modals.createFolder.nameLabel'),
            placeholder: '',
            confirmText: i18n.t('fileExplorer.modals.createFolder.confirm'),
            validate: (candidate: string): string | null => (candidate.trim().length > 0 ? null : i18n.t('fileExplorer.errors.createFolderNameRequired'))
        });
        if (name === null || this.#isDisposed()) {
            return;
        }
        await this.#operations.createDirectory(this.#buildDestinationPath(name.trim()));
    }

    #buildDestinationPath(name: string): string {
        return joinVirtualPath(this.#getCurrentPath(), filenameFromPath(name));
    }
}

export { FileExplorerNewEntryController };

/* SoAI - Shared file explorer browser folder picker modal [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import { folderPickerModalDefinition } from '@core/fileexplorerbrowser/folderPickerModalDom.ts';
import type { FolderPickerModalOptions, FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModalContracts.ts';
import { runFolderPickerModalSession } from '@core/fileexplorerbrowser/folderPickerModalSession.ts';

const showFolderPickerModal = async (options: FolderPickerModalOptions): Promise<FolderPickerResult | null> => {
    return await runFolderPickerModalSession({
        presenter: requireModalPresenter(),
        options
    });
};

const FOLDER_PICKER_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([folderPickerModalDefinition]);

export { FOLDER_PICKER_MODAL_DEFINITIONS, showFolderPickerModal };
export type { FolderPickerModalOptions, FolderPickerResult };

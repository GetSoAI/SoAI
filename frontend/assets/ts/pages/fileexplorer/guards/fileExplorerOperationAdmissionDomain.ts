/* SoAI - File operation admission and accepted outcome presentation lifetime [frontend/assets/ts/pages/fileexplorer/guards/fileExplorerOperationAdmissionDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { isPresentationOwnerActive, isPresentationOwnerMutationAllowed } from '@core/presentationOwner.ts';
import type { FileExplorerControllerHost } from '@pages/fileexplorer/types.ts';

type FileExplorerOperationAdmission = Pick<FileExplorerControllerHost, 'owner' | 'isDirectoryAvailable'>;

const isFileExplorerOperationActive = (host: FileExplorerOperationAdmission, disposed: boolean): boolean => !disposed && isPresentationOwnerActive(host.owner);

const requireFileExplorerOperation = (host: FileExplorerOperationAdmission, disposed: boolean): void => {
    if (!isFileExplorerOperationActive(host, disposed) || !isPresentationOwnerMutationAllowed(host.owner)) throw createAbortError('File operation owner is no longer active');
    if (!host.isDirectoryAvailable()) throw createAbortError('Directory is authoritatively unavailable');
};

export { isFileExplorerOperationActive, requireFileExplorerOperation };

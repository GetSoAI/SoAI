/* SoAI - Existing file text save and rename transaction [frontend/assets/ts/core/fileexplorerbrowser/fileTextSaveTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface ExistingFileTextSaveTransactionRequest {
    sourcePath: string;
    destinationPath: string;
    content: string;
    writeFile: (path: string, content: string) => Promise<void>;
    movePath: (sourcePath: string, destinationPath: string) => Promise<void>;
}

interface ExistingFileTextSaveTransactionOutcome {
    committedPath: string;
    renameError: Error | null;
}

const commitExistingFileTextSaveTransaction = async (request: ExistingFileTextSaveTransactionRequest): Promise<ExistingFileTextSaveTransactionOutcome> => {
    await request.writeFile(request.sourcePath, request.content);
    if (request.destinationPath === request.sourcePath) {
        return { committedPath: request.sourcePath, renameError: null };
    }
    try {
        await request.movePath(request.sourcePath, request.destinationPath);
        return { committedPath: request.destinationPath, renameError: null };
    } catch (error) {
        const renameError = ensureError(error);
        errorHandler.warn('FileTextSaveTransaction', 'File rename failed after the content write committed', renameError);
        return { committedPath: request.sourcePath, renameError };
    }
};

export { commitExistingFileTextSaveTransaction };
export type { ExistingFileTextSaveTransactionOutcome, ExistingFileTextSaveTransactionRequest };

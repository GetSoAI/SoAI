/* SoAI - Shared file explorer browser error messages [frontend/assets/ts/core/fileexplorerbrowser/errorMessages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';

interface FileExplorerBrowserErrorMessages {
    forbidden: () => string;
    missing: () => string;
    precondition: () => string;
    unprocessable?: (message: string) => string;
    fallback: () => string;
}

const resolveFileExplorerBrowserStatusMessage = (error: Error, messages: FileExplorerBrowserErrorMessages): string => {
    if (!(error instanceof APIError)) {
        return messages.fallback();
    }
    if (error.status === 403) {
        return messages.forbidden();
    }
    if (error.status === 404) {
        return messages.missing();
    }
    if (error.status === 412) {
        return messages.precondition();
    }
    if ((error.status === 423 || error.status === 507) && error.message.trim()) {
        return error.message.trim();
    }
    if (error.status === 422 && error.message.trim() && messages.unprocessable) {
        return messages.unprocessable(error.message.trim());
    }
    return messages.fallback();
};

export { resolveFileExplorerBrowserStatusMessage };
export type { FileExplorerBrowserErrorMessages };

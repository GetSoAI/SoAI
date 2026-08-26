/* SoAI - File Explorer content preview object URL controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewObjectUrlController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { revokeFileExplorerContentPreviewMediaUrl } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewMediaController.ts';

class FileExplorerContentPreviewObjectUrlController {
    #url: string | null = null;

    current(): string | null {
        return this.#url;
    }

    replace(url: string | null): void {
        const previousUrl = this.#url;
        this.#url = url;
        if (previousUrl !== url) {
            revokeFileExplorerContentPreviewMediaUrl(previousUrl);
        }
    }

    revoke(): void {
        this.replace(null);
    }
}

export { FileExplorerContentPreviewObjectUrlController };

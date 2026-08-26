/* SoAI - Chat inline media local folder open controller [frontend/assets/ts/pages/chat/controllers/page/actions/openInlineMediaLocalFolderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

interface OpenInlineMediaLocalFolderHost {
    navigateWithQuery(page: string, query: Record<string, string>): void | Promise<void>;
}

const openInlineMediaLocalFolder = async (host: OpenInlineMediaLocalFolderHost, actionElement: HTMLElement): Promise<void> => {
    const folderPath = toTrimmedString(actionElement.dataset['inlineMediaFolderPath'] ?? '');
    if (!folderPath) {
        throw new Error('Inline local folder action requires data-inline-media-folder-path');
    }
    const displayPath = toTrimmedString(actionElement.dataset['inlineMediaFolderLabel'] ?? folderPath) || folderPath;
    const confirmed = await requireDialogsService().showLocalFolderOpenModal({ path: displayPath });
    if (!confirmed) {
        return;
    }
    await host.navigateWithQuery('fileExplorer', { path: folderPath });
};

export { openInlineMediaLocalFolder };
export type { OpenInlineMediaLocalFolderHost };

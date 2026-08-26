/* SoAI - Chat feature inline multimedia folder preview mapping [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaFolderPreviewMapping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileBrowserListPayload } from '@core/fileexplorerbrowser/types.ts';
import type { InlineMediaFolderPreview } from '@features/chat/message/enhancers/inlineMultimediaCardsFiles.ts';

const mapFileExplorerListToFolderPreview = (payload: FileBrowserListPayload): InlineMediaFolderPreview => ({
    total: payload.total,
    entries: payload.entries.map((entry) => ({
        name: entry.name,
        isDirectory: entry.isDirectory
    }))
});

export { mapFileExplorerListToFolderPreview };

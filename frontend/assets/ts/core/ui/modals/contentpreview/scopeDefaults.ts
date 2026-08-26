/* SoAI - Shared UI scope defaults [frontend/assets/ts/core/ui/modals/contentpreview/scopeDefaults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ContentPreviewExternalOpenBehavior, ContentPreviewScope } from '@core/ui/modals/contentpreview/types.ts';

const resolveContentPreviewExternalOpenBehavior = (scope: ContentPreviewScope): ContentPreviewExternalOpenBehavior => {
    if (scope === 'fileExplorer') {
        return 'neverConfirm';
    }
    return 'auto';
};

export { resolveContentPreviewExternalOpenBehavior };

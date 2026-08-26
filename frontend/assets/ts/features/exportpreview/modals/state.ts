/* SoAI - Shared export preview modal state [frontend/assets/ts/features/exportpreview/modals/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ExportPreviewModalState } from '@features/exportpreview/modals/types.ts';

const createExportPreviewModalState = (): ExportPreviewModalState => ({
    isOpen: false,
    scope: '',
    filename: '',
    content: '',
    downloadUrl: '',
    downloadBoundaryName: ''
});

export { createExportPreviewModalState };

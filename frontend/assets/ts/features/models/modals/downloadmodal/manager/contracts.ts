/* SoAI - Models feature manager contracts [frontend/assets/ts/features/models/modals/downloadmodal/manager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DownloadModalState } from '@features/models/modals/downloadmodal/downloadModalState.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';

interface DownloadModalManagerRuntime {
    host: DownloadModalHost;
    state: DownloadModalState;
    modalId: string;
}

export type { DownloadModalManagerRuntime };

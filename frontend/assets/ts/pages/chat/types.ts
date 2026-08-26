/* SoAI - Chat page contracts [frontend/assets/ts/pages/chat/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters } from '@features/chat/public.ts';

export interface NormalizedDetachedParameters {
    conversationId: string | null;
    modelId: string | null;
    sidebarOpen: boolean | null;
    textZoom: number | null;
    searchQuery: string | null;
    parameters: Partial<ChatParameters> | null;
    widescreenMode: boolean | null;
    draftMessage: string | null;
}

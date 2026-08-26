/* SoAI - Prompts page editing, adapter, grouping, and view state ownership [frontend/assets/ts/pages/prompts/controllers/page/PromptsPageSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import { CollectionGroupingState } from '@core/collectionpage/collectionGroupingState.ts';
import { resolveInitialCollectionDisplayMode, type CollectionDisplayMode, type ViewModeController } from '@core/uiprimitives/viewmode/public.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { GroupResolvers } from '@pages/prompts/contracts/contracts.ts';
import type { PromptsApiClient } from '@pages/prompts/contracts/promptsTypes.ts';
import type { PromptDataAdapter } from '@pages/prompts/services/service.ts';
import type { PromptsUiRefs } from '@pages/prompts/types.ts';

const PROMPTS_VIEW_MODE_STORAGE_KEY = 'soai.prompts.viewMode';

class PromptsPageSession {
    ui: PromptsUiRefs | null = null;
    unsavedChangesGuardCleanup: (() => void) | null = null;
    editingPromptId: string | null = null;
    draftPromptId: string | null = null;
    promptsApi: PromptsApiClient | null = null;
    groupResolvers: GroupResolvers | null = null;
    dataAdapter: PromptDataAdapter | null = null;
    dataAdapterReadyTask: Promise<PromptDataAdapter> | null = null;
    viewMode: CollectionDisplayMode = resolveInitialCollectionDisplayMode(PROMPTS_VIEW_MODE_STORAGE_KEY);
    viewModeController: ViewModeController | null = null;
    readonly grouping = new CollectionGroupingState<PromptRecord>();
    viewedPromptId: string | number | null = null;
    cardController: CardPageController | null = null;

    clear(): void {
        this.ui = null;
        this.unsavedChangesGuardCleanup?.();
        this.unsavedChangesGuardCleanup = null;
        this.editingPromptId = null;
        this.draftPromptId = null;
        this.promptsApi = null;
        this.dataAdapterReadyTask = null;
        this.viewModeController = null;
        this.grouping.clear();
        this.viewedPromptId = null;
        this.cardController = null;
    }
}

export { PromptsPageSession };

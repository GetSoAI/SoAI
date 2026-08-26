/* SoAI - Chat prompts picker modal types [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PromptResponse } from '@core/api/contracts/promptContracts.ts';
import type { ResourceListener, ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { PromptPreviewHost, PromptRecord } from '@features/prompts/public.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatPromptsPickerStreamManager {
    subscriptions: {
        subscribeResourceState(resource: string, listener: ResourceListener, options?: { immediate?: boolean; ensureStart?: boolean }): () => void;
    };
    resources: {
        ensureResourceStarted(resource: string, options?: { signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    };
}

interface ChatPromptsPickerModalHost extends PageFeedbackOwnerHost {
    api: ChatPageApi;
    getDocument(): Document;
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    requireStreamManager(): ChatPromptsPickerStreamManager;
    insertPromptContentIntoComposer(content: string): void;
    navigate(page: string): void | Promise<void>;
}

interface ChatPromptsPickerRefs {
    root: HTMLElement;
    searchInput: HTMLInputElement;
    searchButton: HTMLButtonElement;
    results: HTMLElement;
    status: HTMLElement;
    manageButton: HTMLButtonElement;
}

interface ChatPromptsPickerState {
    prompts: PromptRecord[];
    query: string;
    loading: boolean;
    errorMessage: string | null;
}

interface ChatPromptsPickerRenderInput {
    refs: ChatPromptsPickerRefs;
    state: ChatPromptsPickerState;
    visiblePrompts: PromptRecord[];
    getEditIcon(): TrustedHtml;
}

interface ChatPromptsPickerPreviewHost extends PromptPreviewHost {
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptResponse): PromptRecord | null;
}

type PromptSnapshot = ResourceSnapshot;

export type { ChatPromptsPickerModalHost, ChatPromptsPickerPreviewHost, ChatPromptsPickerRefs, ChatPromptsPickerRenderInput, ChatPromptsPickerState, ChatPromptsPickerStreamManager, PromptSnapshot };

/* SoAI - Prompts picker modal types [frontend/assets/ts/features/prompts/picker/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PromptResponse } from '@core/api/contracts/promptContracts.ts';
import type { ResourceListener, ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { PromptPreviewHost } from '@features/prompts/promptPreview.ts';
import type { PromptRecord } from '@features/prompts/promptRecords.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface PromptsPickerStreamManager {
    subscriptions: {
        subscribeResourceState(resource: string, listener: ResourceListener, options?: { immediate?: boolean; ensureStart?: boolean }): () => void;
    };
    resources: {
        ensureResourceStarted(resource: string, options?: { signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    };
}

interface PromptsPickerModalHost extends PageFeedbackOwnerHost {
    promptsApi: PromptPreviewHost['promptsApi'];
    getDocument(): Document;
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    requireStreamManager(): PromptsPickerStreamManager;
    onSelect(content: string): void;
    openLibrary: (() => void | Promise<void>) | null;
}

interface PromptsPickerRefs {
    root: HTMLElement;
    searchInput: HTMLInputElement;
    searchButton: HTMLButtonElement;
    results: HTMLElement;
    status: HTMLElement;
    manageButton: HTMLButtonElement;
}

interface PromptsPickerState {
    prompts: PromptRecord[];
    query: string;
    loading: boolean;
    errorMessage: string | null;
}

interface PromptsPickerRenderInput {
    refs: PromptsPickerRefs;
    state: PromptsPickerState;
    visiblePrompts: PromptRecord[];
    getEditIcon(): TrustedHtml;
}

interface PromptsPickerPreviewHost extends PromptPreviewHost {
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptResponse): PromptRecord | null;
}

type PromptSnapshot = ResourceSnapshot;

export type { PromptsPickerModalHost, PromptsPickerPreviewHost, PromptsPickerRefs, PromptsPickerRenderInput, PromptsPickerState, PromptsPickerStreamManager, PromptSnapshot };

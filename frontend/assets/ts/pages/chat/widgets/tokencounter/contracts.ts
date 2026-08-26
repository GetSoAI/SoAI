/* SoAI - Chat page token counter contracts [frontend/assets/ts/pages/chat/widgets/tokencounter/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonArray, JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { Conversation, StreamUpdate } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

type TokenCounterMode = 'inactive' | 'tokens' | 'rate';

interface TokenCounterHost extends PageDomOwnerHost, PageFeedbackOwnerHost {
    getCurrentConversationId(): string | null;
    getCurrentConversation(): Conversation | null;
    getCurrentModel(): string | null;
    hasSelectableModels(): boolean;
    isModelAvailable(modelId: string): boolean;
    isConversationPersisted(conversationId: string): boolean;
    getRequestParameters(): JsonObject;
    getDraftText(): string;
    getDraftAttachmentContent(): JsonArray;
    subscribeDraftAttachmentChanges(listener: () => void): () => void;
    isTokenCounterInputActionEnabled(): boolean;
    isPageTerminating(): boolean;
    requireTokenCounterButtons(): HTMLButtonElement[];
    requireTokenCounterLabel(button: HTMLButtonElement): HTMLElement;
    runUiTask(operationId: string, task: () => Promise<void> | void): void;
    createDebouncedHandler<TArguments extends JsonValue[]>(functionValue: (...inputArguments: TArguments) => void, delay: number): ((...inputArguments: TArguments) => void) & { cancel: () => void };
    subscribeTokenCounterStreamUpdates(listener: (update: StreamUpdate) => void): () => void;
}

export type { TokenCounterHost, TokenCounterMode };

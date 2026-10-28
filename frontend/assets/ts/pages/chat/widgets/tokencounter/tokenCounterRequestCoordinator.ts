/* SoAI - Chat page token counter request coordinator [frontend/assets/ts/pages/chat/widgets/tokencounter/tokenCounterRequestCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { cloneJsonArray, cloneJsonObject } from '@core/primitives/clone.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { JsonArray, JsonObject } from '@core/types/jsonValues.ts';
import { normalizeConversationId } from '@features/chat/public.ts';
import { serializeChatTokenCountRequest } from '@core/realtime/chatTokenCountRequestContract.ts';
import type { TokenCounterHost } from '@pages/chat/widgets/tokencounter/contracts.ts';
import type { TokenCounterUsageRateTracker } from '@pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts';
import type { ChatTokenCountErrorEvent, ChatTokenCountResultEvent, ConversationBoundEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';

interface TokenCounterWebSocketClient {
    sendMessage(payload: JsonObject, options?: { waitForConnection?: boolean; timeoutMs?: number }): Promise<void>;
}

type TokenCounterRequestPayload = {
    openAiRequest: JsonObject;
    draftUserText: string | null;
    draftAttachmentContent: JsonArray;
    targetInputId?: string | null;
};

type TokenCounterRequest = {
    conversationId: string;
    openAiRequest: JsonObject;
    draftUserText: string | null;
    draftAttachmentContent: JsonArray;
    targetInputId?: string | null;
    generation: number;
    onFailure: () => void;
};

const buildTokenCounterRequestPayload = (host: TokenCounterHost, draftText: string, steeringTargetInputId: string | null): TokenCounterRequestPayload | null => {
    const openAiRequest = cloneJsonObject(host.getRequestParameters());
    const modelId = toTrimmedString(host.getCurrentModel());
    if (!modelId || !host.isModelAvailable(modelId)) {
        return null;
    }
    openAiRequest['model'] = modelId;
    const draftUserText = draftText.trim() ? draftText : null;
    const draftAttachmentContent = cloneJsonArray(host.getDraftAttachmentContent());

    return { openAiRequest, draftUserText, draftAttachmentContent, targetInputId: draftUserText || draftAttachmentContent.length > 0 ? steeringTargetInputId : null };
};

class TokenCounterRequestCoordinator {
    readonly #host: TokenCounterHost;
    readonly #getSteeringTargetInputId: () => string | null;
    readonly #ws: TokenCounterWebSocketClient;
    readonly #usageTracker: TokenCounterUsageRateTracker;
    #activeTokenCountRequestId: string | null = null;
    #activeTokenCountConversationId: string | null = null;
    #activeTokenCountModelId: string | null = null;
    #activeTokenCountTargetInputId: string | null = null;
    #activeTokenCountGeneration = 0;
    #latestTokenCountGeneration = 0;
    #queuedTokenCountRequest: TokenCounterRequest | null = null;

    constructor(options: { getSteeringTargetInputId: () => string | null; host: TokenCounterHost; ws: TokenCounterWebSocketClient; usageTracker: TokenCounterUsageRateTracker }) {
        this.#host = options.host;
        this.#getSteeringTargetInputId = options.getSteeringTargetInputId;
        this.#ws = options.ws;
        this.#usageTracker = options.usageTracker;
    }

    resetActiveRequestId(): void {
        this.#activeTokenCountRequestId = null;
        this.#activeTokenCountConversationId = null;
        this.#activeTokenCountModelId = null;
        this.#activeTokenCountTargetInputId = null;
        this.#activeTokenCountGeneration = 0;
        this.#latestTokenCountGeneration += 1;
        this.#queuedTokenCountRequest = null;
    }

    requestTokenCount(
        inputArguments: TokenCounterRequestPayload & {
            conversationId: string;
            onFailure: () => void;
        }
    ): void {
        if (this.#host.isPageTerminating()) {
            this.resetActiveRequestId();
            return;
        }
        const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
        if (!normalizedConversationId) {
            throw new Error('Token counter request requires a conversation id');
        }
        this.#latestTokenCountGeneration += 1;
        this.#queuedTokenCountRequest = {
            conversationId: normalizedConversationId,
            openAiRequest: inputArguments.openAiRequest,
            draftUserText: inputArguments.draftUserText,
            draftAttachmentContent: inputArguments.draftAttachmentContent,
            targetInputId: inputArguments.targetInputId ?? null,
            generation: this.#latestTokenCountGeneration,
            onFailure: inputArguments.onFailure
        };
        this.#drainTokenCountRequestQueue();
    }

    #drainTokenCountRequestQueue(): void {
        if (this.#host.isPageTerminating()) {
            this.resetActiveRequestId();
            return;
        }
        if (this.#activeTokenCountRequestId !== null) {
            return;
        }
        if (!this.#queuedTokenCountRequest) {
            return;
        }

        const nextRequest = this.#queuedTokenCountRequest;
        this.#queuedTokenCountRequest = null;
        const requestId = `tkc_${generateSecureId()}`;
        const modelId = toTrimmedString(nextRequest.openAiRequest['model']);
        if (!modelId) {
            if (!this.#host.isPageTerminating()) {
                nextRequest.onFailure();
            }
            this.#drainTokenCountRequestQueue();
            return;
        }
        this.#activeTokenCountRequestId = requestId;
        this.#activeTokenCountConversationId = nextRequest.conversationId;
        this.#activeTokenCountModelId = modelId;
        this.#activeTokenCountTargetInputId = nextRequest.targetInputId ?? null;
        this.#activeTokenCountGeneration = nextRequest.generation;

        const payload = serializeChatTokenCountRequest({
            conversationId: nextRequest.conversationId,
            requestId,
            openAiRequest: nextRequest.openAiRequest,
            draftUserText: nextRequest.draftUserText,
            draftAttachmentContent: nextRequest.draftAttachmentContent,
            targetInputId: nextRequest.targetInputId ?? null
        });

        this.#host.runUiTask(`chat:tokenCounter:request:${requestId}`, async (): Promise<void> => {
            if (!this.#isActiveRequestContextCurrent(requestId, nextRequest.conversationId, modelId, nextRequest.generation)) {
                this.#clearActiveRequest(requestId);
                return;
            }
            try {
                await this.#ws.sendMessage(payload, { waitForConnection: true, timeoutMs: 15000 });
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('ChatPage', 'Chat token counter request failed', runtimeError);
                if (this.#host.isPageTerminating()) {
                    this.#clearActiveRequest(requestId);
                    return;
                }
                if (this.#activeTokenCountRequestId === requestId) {
                    const shouldNotifyFailure = this.#isActiveRequestContextCurrent(requestId, nextRequest.conversationId, modelId, nextRequest.generation);
                    this.#clearActiveRequest(requestId);
                    if (shouldNotifyFailure) {
                        nextRequest.onFailure();
                    }
                }
            }
        });
    }

    #clearActiveRequest(requestId: string): void {
        if (this.#activeTokenCountRequestId !== requestId) {
            return;
        }
        this.#activeTokenCountRequestId = null;
        this.#activeTokenCountConversationId = null;
        this.#activeTokenCountModelId = null;
        this.#activeTokenCountTargetInputId = null;
        this.#activeTokenCountGeneration = 0;
        if (this.#host.isPageTerminating()) {
            this.#queuedTokenCountRequest = null;
            return;
        }
        this.#drainTokenCountRequestQueue();
    }

    #isActiveRequestContextCurrent(requestId: string, conversationId: string, modelId: string | null, generation: number): boolean {
        if (this.#activeTokenCountRequestId !== requestId) {
            return false;
        }
        if (this.#activeTokenCountGeneration !== generation || this.#latestTokenCountGeneration !== generation) {
            return false;
        }
        if (this.#activeTokenCountConversationId !== conversationId) {
            return false;
        }
        if (this.#activeTokenCountModelId !== modelId) {
            return false;
        }
        if (normalizeConversationId(this.#host.getCurrentConversationId()) !== conversationId) {
            return false;
        }
        if (this.#activeTokenCountTargetInputId !== this.#getSteeringTargetInputId()) return false;
        const currentModelId = toTrimmedString(this.#host.getCurrentModel());
        return Boolean(currentModelId) && currentModelId === modelId && this.#host.isModelAvailable(currentModelId);
    }

    #isActiveRequestCurrent(event: ConversationBoundEvent, requestId: string): boolean {
        if (this.#activeTokenCountRequestId !== requestId) {
            return false;
        }
        const conversationId = normalizeConversationId(event.convId);
        if (!conversationId) {
            this.#clearActiveRequest(requestId);
            return false;
        }
        if (conversationId !== this.#activeTokenCountConversationId) {
            this.#clearActiveRequest(requestId);
            return false;
        }
        if (!this.#isActiveRequestContextCurrent(requestId, conversationId, this.#activeTokenCountModelId, this.#activeTokenCountGeneration)) {
            this.#clearActiveRequest(requestId);
            return false;
        }
        return true;
    }

    handleTokenCountResult(event: ChatTokenCountResultEvent): boolean {
        if (this.#host.isPageTerminating()) {
            this.resetActiveRequestId();
            return false;
        }
        const normalizedRequestId = event.requestId;
        if (!this.#isActiveRequestCurrent(event, normalizedRequestId)) {
            return false;
        }
        const applied = this.#activeTokenCountTargetInputId !== null ? this.#usageTracker.setSteeringPreview(event.usagePreview) : this.#usageTracker.setPromptUsageSnapshot(event.usagePreview);
        if (!applied) {
            this.#clearActiveRequest(normalizedRequestId);
            return false;
        }
        this.#clearActiveRequest(normalizedRequestId);
        return true;
    }

    handleTokenCountError(event: ChatTokenCountErrorEvent): boolean {
        if (this.#host.isPageTerminating()) {
            this.resetActiveRequestId();
            return false;
        }
        const normalizedRequestId = event.requestId;
        if (!this.#isActiveRequestCurrent(event, normalizedRequestId)) {
            return false;
        }
        this.#clearActiveRequest(normalizedRequestId);
        return true;
    }
}

export { TokenCounterRequestCoordinator, buildTokenCounterRequestPayload };
export type { TokenCounterRequestPayload };

/* SoAI - Assistant stream-state hydration policy [frontend/assets/ts/features/chat/chatstreamservice/assistantStreamStateHydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { getWindow } from '@core/environment/public.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasTerminalThinkingActivityStatusRegression } from '@features/chat/assistanteventtimeline/activityState.ts';
import { normalizeAssistantStreamStatePayloadForIdentity, type AssistantStreamStateIdentity } from '@features/chat/chatstreamservice/assistantStreamStatePayload.ts';
import { fetchAssistantStreamState, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import { resolveHydrationDeadlineAtMs, resolveHydrationRetryDelayMs } from '@features/chat/chatstreamservice/hydrationTiming.ts';
import { resolveHydratedTerminalStatusFromMessage } from '@features/chat/chatstreamservice/streamHydratedTerminalStatus.ts';

type AssistantStreamStateHydrationIdentity = AssistantStreamStateIdentity & {
    conversationId: string;
};

type AssistantStreamStateHydrationArguments = {
    apiClient: ChatStreamApiClient;
    identity: AssistantStreamStateHydrationIdentity;
    initialMessage: ChatMessage | null;
    requireTerminal: boolean;
    shouldContinue: () => boolean;
    signal?: AbortSignal | undefined;
};

const isAssistantStreamStatePendingError = (error: Error): boolean => {
    return error instanceof APIError && error.status === 404;
};

const messageSatisfiesHydrationRequirement = (message: ChatMessage, initialMessage: ChatMessage | null, requireTerminal: boolean): boolean => {
    if (initialMessage !== null && hasTerminalThinkingActivityStatusRegression(initialMessage, message)) {
        return false;
    }
    return !requireTerminal || resolveHydratedTerminalStatusFromMessage(message) !== null;
};

const fetchAssistantStreamStateSnapshot = async (inputArguments: AssistantStreamStateHydrationArguments): Promise<ChatMessage | null> => {
    try {
        const payload = await fetchAssistantStreamState(inputArguments.apiClient, inputArguments.identity.conversationId, inputArguments.identity.assistantTurnTimestamp, inputArguments.identity.modelVariantIndex, inputArguments.signal);
        const hydratedMessage = normalizeAssistantStreamStatePayloadForIdentity(payload, inputArguments.identity);
        if (hydratedMessage === null || !messageSatisfiesHydrationRequirement(hydratedMessage, inputArguments.initialMessage, inputArguments.requireTerminal)) {
            return null;
        }
        return hydratedMessage;
    } catch (error) {
        if (error instanceof Error && isAssistantStreamStatePendingError(error)) {
            return null;
        }
        throw error;
    }
};

const waitForAssistantStreamStateSnapshot = async (inputArguments: AssistantStreamStateHydrationArguments): Promise<ChatMessage | null> => {
    if (!inputArguments.shouldContinue()) {
        return null;
    }
    if (inputArguments.initialMessage !== null && messageSatisfiesHydrationRequirement(inputArguments.initialMessage, inputArguments.initialMessage, inputArguments.requireTerminal)) {
        return inputArguments.initialMessage;
    }
    const deadlineAtMs = resolveHydrationDeadlineAtMs();
    let retryAttempt = 0;
    while (monotonicMs() < deadlineAtMs) {
        if (!inputArguments.shouldContinue()) {
            return null;
        }
        const hydratedMessage = await fetchAssistantStreamStateSnapshot(inputArguments);
        if (!inputArguments.shouldContinue()) {
            return null;
        }
        if (hydratedMessage !== null) {
            return hydratedMessage;
        }
        const delayMs = resolveHydrationRetryDelayMs(retryAttempt, deadlineAtMs);
        if (delayMs <= 0) {
            break;
        }
        retryAttempt += 1;
        await waitForTimerDelay(getWindow(), delayMs, inputArguments.signal ?? null);
    }
    return null;
};

export { waitForAssistantStreamStateSnapshot };
export type { AssistantStreamStateHydrationIdentity };

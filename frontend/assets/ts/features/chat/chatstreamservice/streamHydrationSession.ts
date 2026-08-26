/* SoAI - Chat stream hydration polling [frontend/assets/ts/features/chat/chatstreamservice/streamHydrationSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import { normalizeAssistantStreamStatePayloadForIdentity } from '@features/chat/chatstreamservice/assistantStreamStatePayload.ts';
import { fetchAssistantStreamState, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import { normalizeRequiredHydrationSequence, resolveHydrationDeadlineAtMs, resolveHydrationRetryDelayMs } from '@features/chat/chatstreamservice/hydrationTiming.ts';
import type { ChatStreamEventPump } from '@features/chat/chatstreamservice/streamRunSessionEventPump.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type FetchStreamState = (convId: string, assistantTurnTimestamp: number, modelVariantIndex: number) => Promise<ChatMessage | undefined>;
type Sleep = (ms: number) => Promise<void>;
type ChatStreamHydrationResult =
    | {
          status: 'hydrated';
          progressRevision: number;
          requiredSequence: number;
      }
    | {
          status: 'recoverable';
          progressRevision: number;
          requiredSequence: number;
      }
    | {
          status: 'inactive';
          progressRevision: number;
          requiredSequence: number;
      };

class ChatStreamHydrationSession {
    readonly #convId: string;
    readonly #session: ChatStreamSession;
    readonly #pump: ChatStreamEventPump;
    readonly #fetchStreamState: FetchStreamState;
    readonly #onSharedStreamState: (() => void) | null;
    readonly #timers: ResourceTracker;
    #deadlineAtMs: number;
    readonly #sleepFunctionValue: Sleep | null;
    #requiredSequence: number;
    #inFlight: Promise<ChatStreamHydrationResult> | null;
    #pendingSleep: Deferred<void> | null;
    #disposed: boolean;

    constructor(inputArguments: { convId: string; session: ChatStreamSession; pump: ChatStreamEventPump; fetchStreamState: FetchStreamState; onSharedStreamState?: (() => void) | null; sleep?: Sleep | null }) {
        this.#convId = inputArguments.convId;
        this.#session = inputArguments.session;
        this.#pump = inputArguments.pump;
        this.#fetchStreamState = inputArguments.fetchStreamState;
        this.#onSharedStreamState = inputArguments.onSharedStreamState ?? null;
        this.#timers = new ResourceTracker();
        this.#deadlineAtMs = 0;
        this.#sleepFunctionValue = inputArguments.sleep ?? null;
        this.#requiredSequence = 0;
        this.#inFlight = null;
        this.#pendingSleep = null;
        this.#disposed = false;
    }

    dispose(): void {
        this.#disposed = true;
        this.#pendingSleep?.resolve();
        this.#pendingSleep = null;
        this.#timers.cleanup();
        this.#inFlight = null;
    }

    async request(requiredSequence: number): Promise<ChatStreamHydrationResult> {
        if (this.#disposed) {
            return { status: 'inactive', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: 0 };
        }
        const required = normalizeRequiredHydrationSequence(requiredSequence);
        const previousRequiredSequence = this.#requiredSequence;
        this.#requiredSequence = Math.max(this.#requiredSequence, required);
        this.#deadlineAtMs = resolveHydrationDeadlineAtMs();
        if (this.#inFlight) {
            if (this.#requiredSequence > previousRequiredSequence) {
                this.#pendingSleep?.resolve();
            }
            return await this.#inFlight;
        }
        this.#inFlight = this.#hydrateUntilRequiredPrefix().finally(() => {
            this.#inFlight = null;
        });
        return await this.#inFlight;
    }

    async #hydrateUntilRequiredPrefix(): Promise<ChatStreamHydrationResult> {
        let retryAttempt = 0;
        let previousRequiredPrefix = -1;
        while (!this.#disposed && monotonicMs() < this.#deadlineAtMs && this.#session.active && this.#session.status === 'streaming') {
            const requiredPrefix = this.#requiredSequence;
            if (requiredPrefix > previousRequiredPrefix) {
                retryAttempt = 0;
                previousRequiredPrefix = requiredPrefix;
            }
            let payload: ChatMessage | undefined;
            try {
                payload = await this.#fetchStreamState(this.#convId, this.#session.assistantTurnTimestamp, this.#session.modelVariantIndex);
            } catch {
                if (this.#disposed || !this.#session.active || this.#session.status !== 'streaming') {
                    return { status: 'inactive', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: this.#requiredSequence };
                }
                const delayMs = resolveHydrationRetryDelayMs(retryAttempt, this.#deadlineAtMs);
                if (delayMs <= 0) {
                    break;
                }
                retryAttempt += 1;
                await this.#sleep(delayMs);
                continue;
            }
            if (this.#disposed || !this.#session.active || this.#session.status !== 'streaming') {
                return { status: 'inactive', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: this.#requiredSequence };
            }
            const hydratedMessage = normalizeAssistantStreamStatePayloadForIdentity(payload, {
                assistantTimestamp: this.#session.assistantTimestamp,
                assistantTurnTimestamp: this.#session.assistantTurnTimestamp,
                modelVariantIndex: this.#session.modelVariantIndex
            });
            if (hydratedMessage === null) {
                throw new Error('Stream hydration received a malformed or identity-mismatched assistant stream-state payload.');
            }
            await this.#pump.applyHydratedSnapshot(hydratedMessage, { resume: false, onSharedStreamState: this.#onSharedStreamState ?? undefined });
            if (this.#disposed || !this.#session.active || this.#session.status !== 'streaming') {
                return { status: 'inactive', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: this.#requiredSequence };
            }
            const appliedProgress = resolveAssistantTimelineProgress(this.#session.assistantMessage);
            const currentRequiredSequence = this.#requiredSequence;
            if (appliedProgress.assistantRevision >= currentRequiredSequence) {
                this.#pump.resume();
                return { status: 'hydrated', progressRevision: appliedProgress.assistantRevision, requiredSequence: currentRequiredSequence };
            }
            const delayMs = resolveHydrationRetryDelayMs(retryAttempt, this.#deadlineAtMs);
            if (delayMs <= 0) {
                break;
            }
            retryAttempt += 1;
            await this.#sleep(delayMs);
        }
        if (this.#disposed || !this.#session.active || this.#session.status !== 'streaming') {
            return { status: 'inactive', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: this.#requiredSequence };
        }
        return { status: 'recoverable', progressRevision: resolveAssistantTimelineProgress(this.#session.assistantMessage).assistantRevision, requiredSequence: this.#requiredSequence };
    }

    async #sleep(ms: number): Promise<void> {
        if (this.#disposed) {
            return;
        }
        const deferred = createDeferred<void>();
        this.#pendingSleep = deferred;
        const clearPendingSleep = (): void => {
            if (this.#pendingSleep === deferred) {
                this.#pendingSleep = null;
            }
        };
        if (this.#sleepFunctionValue) {
            try {
                await Promise.race([this.#sleepFunctionValue(ms), deferred.promise]).finally(clearPendingSleep);
                return;
            } catch (error) {
                clearPendingSleep();
                throw ensureError(error);
            }
        }
        this.#timers.setTimeout((): void => {
            clearPendingSleep();
            deferred.resolve();
        }, ms);
        await deferred.promise;
    }
}

const buildDefaultFetchStreamState = (apiClient: ChatStreamApiClient, fetch: FetchStreamState | null | undefined): FetchStreamState => {
    if (fetch) {
        return fetch;
    }
    return async (convId: string, assistantTurnTimestamp: number, modelVariantIndex: number): Promise<ChatMessage | undefined> => {
        return await fetchAssistantStreamState(apiClient, convId, assistantTurnTimestamp, modelVariantIndex);
    };
};

export { ChatStreamHydrationSession, buildDefaultFetchStreamState };
export type { ChatStreamHydrationResult, FetchStreamState };

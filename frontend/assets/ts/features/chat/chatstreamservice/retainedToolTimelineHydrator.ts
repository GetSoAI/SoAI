/* SoAI - Chat feature retained tool timeline hydrator [frontend/assets/ts/features/chat/chatstreamservice/retainedToolTimelineHydrator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { commitAssistantSnapshot, prepareAssistantSnapshot } from '@features/chat/chatstreamservice/assistantSnapshotTransaction.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import { normalizeAssistantStreamStatePayloadForIdentity } from '@features/chat/chatstreamservice/assistantStreamStatePayload.ts';
import { fetchAssistantStreamState, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { normalizeRequiredHydrationSequence, resolveHydrationDeadlineAtMs, resolveHydrationRetryDelayMs } from '@features/chat/chatstreamservice/hydrationTiming.ts';
import type { ChatStreamIdentityKey } from '@features/chat/chatstreamservice/streamIdentity.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

export class RetainedToolTimelineHydrator {
    readonly #apiClient: ChatStreamApiClient;
    readonly #runtime: StreamRuntime;
    readonly #hydrationInFlightByKey = new Map<ChatStreamIdentityKey, Promise<void>>();
    readonly #sequenceHydrationInFlightByKey = new Map<ChatStreamIdentityKey, Promise<void>>();
    readonly #requiredSequenceByKey = new Map<ChatStreamIdentityKey, number>();
    readonly #deadlineAtMsByKey = new Map<ChatStreamIdentityKey, number>();
    readonly #pendingSleepByKey = new Map<ChatStreamIdentityKey, Deferred<void>>();
    #disposed: boolean;

    constructor(inputArguments: { apiClient: ChatStreamApiClient; runtime: StreamRuntime }) {
        this.#apiClient = inputArguments.apiClient;
        this.#runtime = inputArguments.runtime;
        this.#disposed = false;
    }

    dispose(): void {
        this.#disposed = true;
        for (const pendingSleep of this.#pendingSleepByKey.values()) {
            pendingSleep.resolve();
        }
        this.#pendingSleepByKey.clear();
        this.#hydrationInFlightByKey.clear();
        this.#sequenceHydrationInFlightByKey.clear();
        this.#requiredSequenceByKey.clear();
        this.#deadlineAtMsByKey.clear();
    }

    async hydrateStreamState(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession, shouldApply: () => boolean): Promise<void> {
        if (this.#disposed) {
            return;
        }
        const inFlight = this.#hydrationInFlightByKey.get(key);
        if (inFlight) {
            await inFlight;
            return;
        }
        const promise = this.#hydrateOnce(convId, session, shouldApply).finally(() => {
            this.#hydrationInFlightByKey.delete(key);
        });
        this.#hydrationInFlightByKey.set(key, promise);
        await promise;
    }

    async hydrateStreamStateUntilSequence(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession, requiredSequence: number, shouldApply: () => boolean): Promise<void> {
        if (this.#disposed) {
            return;
        }
        const normalizedRequiredSequence = normalizeRequiredHydrationSequence(requiredSequence);
        const existingRequiredSequence = this.#requiredSequenceByKey.get(key) ?? 0;
        this.#requiredSequenceByKey.set(key, Math.max(existingRequiredSequence, normalizedRequiredSequence));
        this.#deadlineAtMsByKey.set(key, resolveHydrationDeadlineAtMs());
        if (normalizedRequiredSequence > existingRequiredSequence) {
            this.#pendingSleepByKey.get(key)?.resolve();
        }
        const inFlight = this.#sequenceHydrationInFlightByKey.get(key);
        if (inFlight) {
            await inFlight;
            return;
        }
        const promise = this.#hydrateStreamStateUntilCurrentSequence(key, convId, session, shouldApply).finally(() => {
            this.#sequenceHydrationInFlightByKey.delete(key);
            this.#requiredSequenceByKey.delete(key);
            this.#deadlineAtMsByKey.delete(key);
            this.#pendingSleepByKey.delete(key);
        });
        this.#sequenceHydrationInFlightByKey.set(key, promise);
        await promise;
    }

    async #hydrateStreamStateUntilCurrentSequence(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession, shouldApply: () => boolean): Promise<void> {
        let retryAttempt = 0;
        let previousRequiredSequence = -1;
        while (!this.#disposed && shouldApply()) {
            const deadlineAtMs = this.#deadlineAtMsByKey.get(key) ?? 0;
            if (monotonicMs() >= deadlineAtMs) {
                break;
            }
            const normalizedRequiredSequence = this.#requiredSequenceByKey.get(key) ?? 0;
            if (normalizedRequiredSequence > previousRequiredSequence) {
                retryAttempt = 0;
                previousRequiredSequence = normalizedRequiredSequence;
            }
            await this.hydrateStreamState(key, convId, session, shouldApply);
            if (this.#disposed || !shouldApply()) {
                return;
            }
            const progress = resolveAssistantTimelineProgress(session.assistantMessage);
            const currentRequiredSequence = this.#requiredSequenceByKey.get(key) ?? 0;
            if (progress.assistantRevision >= currentRequiredSequence) {
                return;
            }
            const delayMs = resolveHydrationRetryDelayMs(retryAttempt, deadlineAtMs);
            if (delayMs <= 0) {
                break;
            }
            retryAttempt += 1;
            await this.#sleep(key, delayMs);
        }
        if (this.#disposed || !shouldApply()) {
            return;
        }
        throw new Error('Retained stream failed to hydrate a contiguous prefix within the deadline.');
    }

    async #hydrateOnce(convId: string, session: ChatStreamSession, shouldApply: () => boolean): Promise<void> {
        if (this.#disposed) {
            return;
        }
        let payload: ChatMessage | undefined;
        try {
            payload = await fetchAssistantStreamState(this.#apiClient, convId, session.assistantTurnTimestamp, session.modelVariantIndex);
        } catch (error) {
            if (this.#disposed || !shouldApply()) {
                return;
            }
            throw ensureError(error);
        }
        if (this.#disposed || !shouldApply()) {
            return;
        }
        const assistantMessage = normalizeAssistantStreamStatePayloadForIdentity(payload, {
            assistantTimestamp: session.assistantTimestamp,
            assistantTurnTimestamp: session.assistantTurnTimestamp,
            modelVariantIndex: session.modelVariantIndex
        });
        if (assistantMessage === null) {
            throw new Error('Retained stream hydration returned an invalid assistant stream state payload.');
        }
        const progress = resolveAssistantTimelineProgress(assistantMessage);
        const currentProgress = resolveAssistantTimelineProgress(session.assistantMessage);
        if (progress.assistantRevision <= currentProgress.assistantRevision) {
            return;
        }
        const prepared = prepareAssistantSnapshot(session, assistantMessage);
        if (prepared === null) return;
        commitAssistantSnapshot(session, prepared);
        this.#runtime.notify(session, { type: 'timeline-event' });
    }

    async #sleep(key: ChatStreamIdentityKey, ms: number): Promise<void> {
        if (this.#disposed) {
            return;
        }
        const deferred = createDeferred<void>();
        this.#pendingSleepByKey.set(key, deferred);
        const clearPendingSleep = (): void => {
            if (this.#pendingSleepByKey.get(key) === deferred) {
                this.#pendingSleepByKey.delete(key);
            }
        };
        await Promise.race([sleepMs(ms), deferred.promise]).finally(clearPendingSleep);
    }
}

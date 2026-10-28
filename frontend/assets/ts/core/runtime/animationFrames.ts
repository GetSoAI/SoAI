/* SoAI - Shared frontend runtime animation frames [frontend/assets/ts/core/runtime/animationFrames.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getMessageChannelCtor, getRequestAnimationFrame, requireDocument } from '@core/environment/public.ts';
import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

type PresentationFrameOutcome = 'frame' | 'hidden';
type HiddenFramePolicy = 'wait' | 'skip' | 'render';

interface FrameSchedulerOptions {
    requestAnimationFrame?: ((callback: () => void) => number) | undefined;
    cancelAnimationFrame?: ((identifier: number) => void) | undefined;
}

const scheduleFrame = (callback: (outcome: PresentationFrameOutcome) => void, hiddenPolicy: HiddenFramePolicy, options: FrameSchedulerOptions = {}): (() => void) => {
    const document = requireDocument();
    const requestFrame = options.requestAnimationFrame ?? getRequestAnimationFrame();
    const cancelFrame = options.cancelAnimationFrame ?? getCancelAnimationFrame();
    const MessageChannelConstructor = hiddenPolicy === 'render' ? getMessageChannelCtor() : null;
    let frameIdentifier: number | null = null;
    let channel: MessageChannel | null = null;
    let active = true;
    let generation = 0;

    const clearScheduled = (): void => {
        generation += 1;
        if (frameIdentifier !== null) cancelFrame(frameIdentifier);
        frameIdentifier = null;
        if (channel !== null) {
            channel.port1.onmessage = null;
            channel.port1.close();
            channel.port2.close();
            channel = null;
        }
    };
    const cancel = (): void => {
        active = false;
        document.removeEventListener('visibilitychange', schedule);
        clearScheduled();
    };
    const complete = (scheduledGeneration: number, outcome: PresentationFrameOutcome): void => {
        if (!active || generation !== scheduledGeneration) return;
        cancel();
        callback(outcome);
    };
    const schedule = (): void => {
        if (!active) return;
        clearScheduled();
        const scheduledGeneration = generation;
        if (hiddenPolicy !== 'wait' && document.visibilityState === 'hidden') {
            if (MessageChannelConstructor === null) {
                complete(scheduledGeneration, 'hidden');
                return;
            }
            channel = new MessageChannelConstructor();
            channel.port1.onmessage = () => complete(scheduledGeneration, 'hidden');
            channel.port2.postMessage(null);
            return;
        }
        frameIdentifier = requestFrame(() => complete(scheduledGeneration, 'frame'));
    };
    if (hiddenPolicy !== 'wait') document.addEventListener('visibilitychange', schedule);
    try {
        schedule();
    } catch (error) {
        cancel();
        throw error;
    }
    return cancel;
};

const awaitFrame = async (signal: AbortSignal | null, message: string, hiddenPolicy: 'wait' | 'skip'): Promise<PresentationFrameOutcome> => {
    throwIfAborted(signal, message);
    const completion = createDeferred<PresentationFrameOutcome>();
    let cancelFrame = (): void => {};
    const onAbort = (): void => {
        cancelFrame();
        completion.reject(createAbortError(message));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
    try {
        cancelFrame = scheduleFrame(completion.resolve, hiddenPolicy);
        const outcome = await completion.promise;
        throwIfAborted(signal, message);
        return outcome;
    } finally {
        signal?.removeEventListener('abort', onAbort);
        cancelFrame();
    }
};

const awaitAnimationFrame = async (signal: AbortSignal | null, message: string): Promise<void> => {
    await awaitFrame(signal, message, 'wait');
};

const awaitPresentationFrame = (signal: AbortSignal | null, message: string): Promise<PresentationFrameOutcome> => awaitFrame(signal, message, 'skip');

const scheduleRequiredRender = (callback: (outcome: PresentationFrameOutcome) => void, options: FrameSchedulerOptions = {}): (() => void) => scheduleFrame(callback, 'render', options);

export { awaitAnimationFrame, awaitPresentationFrame, scheduleRequiredRender };
export type { PresentationFrameOutcome };

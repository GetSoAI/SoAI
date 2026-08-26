/* SoAI - Chat feature stream run session event pump [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionEventPump.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import { applyStreamEventToSession } from '@features/chat/chatstreamservice/streamRunSessionEventApplication.ts';
import { commitAssistantSnapshot, prepareAssistantSnapshot } from '@features/chat/chatstreamservice/assistantSnapshotTransaction.ts';
import { applyCancelledStreamEvent, applyCompletedStreamEvent, applyErrorStreamEvent } from '@features/chat/chatstreamservice/streamTerminalEventApplication.ts';
import { ChatStreamFirstServerEventHookError } from '@features/chat/chatstreamservice/streamRunSessionErrors.ts';
import { parseChatStreamEventEnvelope, type ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { resolveSequenceMismatchPolicy, type SequenceMismatchDecision, type SequenceMismatchPolicy } from '@features/chat/chatstreamservice/streamRunSessionSequenceMismatchPolicy.ts';
import { applyChatStreamCommandErrorEnvelope } from '@features/chat/chatstreamservice/streamRunSessionCommandErrorApplication.ts';
import { parseChatStreamCommandErrorEnvelope, type ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { chatStreamEnvelopeMatchesSession, isChatStreamNonNegativeInteger } from '@features/chat/chatstreamservice/streamPayloadValidation.ts';

type FailProtocol = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null, cancelReason?: string | null) => void;
type MarkDone = () => void;
type IsDone = () => boolean;
type OnMatchedStreamEvent = () => Promise<void> | void;
type MarkThrowAfterFinally = (error: Error) => void;
const CHAT_STREAM_EVENT_QUEUE_LIMIT = 2048;
const CHAT_STREAM_EVENT_QUEUE_OVERFLOW_CODE = 'client_event_queue_overflow';

interface ChatStreamEventPump {
    handleStreamEvent(data: JsonValue): void;
    handleStreamEnvelope(envelope: ChatStreamEventEnvelope): void;
    handleCommandErrorEvent(data: JsonValue): void;
    handleCommandErrorEnvelope(envelope: ChatStreamCommandErrorEnvelope): void;
    waitForQueuedStreamEvents(): Promise<void>;
    applyHydratedSnapshot(message: ChatMessage, options?: { resume?: boolean | undefined; onSharedStreamState?: (() => void) | undefined; notifyUserOnTerminal?: boolean | undefined }): Promise<HydratedSnapshotApplicationResult>;
    resume(): void;
}

const createChatStreamEventPump = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; failProtocol: FailProtocol; markDone: MarkDone; isDone: IsDone; onMatchedStreamEvent: OnMatchedStreamEvent; markThrowAfterFinally: MarkThrowAfterFinally; sequenceMismatchPolicy?: SequenceMismatchPolicy | null }): ChatStreamEventPump => {
    const { session, runtime, failProtocol, markDone, isDone, onMatchedStreamEvent, markThrowAfterFinally } = inputArguments;
    let paused = false;
    const envelopeQueue: ChatStreamEventEnvelope[] = [];
    let envelopeQueueReadIndex = 0;
    let drainInFlight: Promise<void> | null = null;
    let hydrationInFlight: Promise<HydratedSnapshotApplicationResult> | null = null;
    let commandErrorInFlight: Promise<void> = Promise.resolve();
    const sequenceMismatchPolicy = resolveSequenceMismatchPolicy(inputArguments.sequenceMismatchPolicy);

    const runFirstServerEventHook = async (): Promise<void> => {
        if (session.firstServerEventHandled) {
            return;
        }
        session.firstServerEventHandled = true;
        const hook = session.onFirstServerEvent;
        if (!hook) {
            return;
        }
        try {
            await hook();
        } catch (error) {
            const runtimeError = ensureError(error);
            session.pendingCancellation = { reason: `Client hook failed: ${runtimeError.message}` };
            session.abortController.abort();
            throw new ChatStreamFirstServerEventHookError('Chat stream first-server-event hook failed.', runtimeError);
        }
    };

    const handleEvent = async (envelope: ChatStreamEventEnvelope): Promise<void> => {
        if (isDone()) {
            return;
        }
        await applyStreamEventToSession({ event: envelope, session, runtime, failProtocol, markDone, notifyUser: true });
    };

    const failProcessing = (error: Error): void => {
        if (isDone()) {
            return;
        }
        const runtimeError = ensureError(error);
        const errorCode = error instanceof ChatStreamFirstServerEventHookError ? 'client_hook_failed' : null;
        if (error instanceof ChatStreamFirstServerEventHookError) {
            markThrowAfterFinally(error);
        }
        failProtocol(runtimeError.message, errorCode);
    };

    const pauseForSequenceMismatch = async (expectedSequence: number, envelope: ChatStreamEventEnvelope): Promise<void> => {
        paused = true;
        const decision = await sequenceMismatchPolicy.decide({
            expectedSequence,
            receivedSequence: envelope.sequence,
            envelope
        });
        if (decision.action === 'pause') {
            return;
        }
        paused = false;
        failProtocol(decision.message, decision.errorCode, null, decision.cancelReason);
    };

    const processEnvelope = async (envelope: ChatStreamEventEnvelope): Promise<void> => {
        if (isDone()) {
            return;
        }
        if (!chatStreamEnvelopeMatchesSession(envelope, session)) {
            return;
        }
        await onMatchedStreamEvent();
        if (isDone()) {
            return;
        }
        const seq = envelope.sequence;
        if (!isChatStreamNonNegativeInteger(seq)) {
            return;
        }
        let expectedSequence = session.assistantRevision;
        if (seq < expectedSequence) {
            return;
        }
        if (seq !== expectedSequence) {
            await pauseForSequenceMismatch(expectedSequence, envelope);
            return;
        }
        await runFirstServerEventHook();
        if (isDone()) {
            return;
        }
        expectedSequence = session.assistantRevision;
        if (seq < expectedSequence) {
            return;
        }
        if (seq !== expectedSequence) {
            await pauseForSequenceMismatch(expectedSequence, envelope);
            return;
        }
        await handleEvent(envelope);
    };

    const drainQueue = async (): Promise<void> => {
        while (!isDone() && !paused && envelopeQueueReadIndex < envelopeQueue.length) {
            const envelope = envelopeQueue[envelopeQueueReadIndex];
            if (!envelope) {
                envelopeQueueReadIndex += 1;
                continue;
            }
            await processEnvelope(envelope);
            if (isDone()) {
                return;
            }
            if (paused) {
                return;
            }
            envelopeQueueReadIndex += 1;
        }
        if (envelopeQueueReadIndex <= 0) {
            return;
        }
        if (envelopeQueueReadIndex >= envelopeQueue.length) {
            envelopeQueue.length = 0;
            envelopeQueueReadIndex = 0;
            return;
        }
        if (envelopeQueueReadIndex >= 1024) {
            envelopeQueue.splice(0, envelopeQueueReadIndex);
            envelopeQueueReadIndex = 0;
        }
    };

    const scheduleDrain = (): void => {
        if (isDone() || drainInFlight || hydrationInFlight) {
            return;
        }
        if (paused) {
            return;
        }
        drainInFlight = drainQueue()
            .catch((error) => {
                failProcessing(ensureError(error));
            })
            .finally(() => {
                drainInFlight = null;
                if (!isDone() && !paused && envelopeQueueReadIndex < envelopeQueue.length) {
                    scheduleDrain();
                }
            });
    };

    const waitForQueuedStreamEvents = async (): Promise<void> => {
        if (isDone()) return;
        await hydrationInFlight;
        if (!drainInFlight && envelopeQueueReadIndex < envelopeQueue.length) {
            scheduleDrain();
        }
        await drainInFlight;
    };

    const handleStreamEnvelope = (envelope: ChatStreamEventEnvelope): void => {
        if (isDone()) {
            return;
        }
        const unconsumedEnvelopeCount = envelopeQueue.length - envelopeQueueReadIndex;
        if (unconsumedEnvelopeCount >= CHAT_STREAM_EVENT_QUEUE_LIMIT) {
            envelopeQueue.length = 0;
            envelopeQueueReadIndex = 0;
            paused = false;
            failProtocol('Chat stream recovery exceeded the safe client buffer limit.', CHAT_STREAM_EVENT_QUEUE_OVERFLOW_CODE, null, 'Chat stream recovery buffer overflow');
            return;
        }
        envelopeQueue.push(envelope);
        scheduleDrain();
    };

    const handleStreamEvent = (data: JsonValue): void => {
        const envelope = parseChatStreamEventEnvelope(data);
        if (envelope) {
            handleStreamEnvelope(envelope);
        }
    };

    const handleCommandErrorEnvelope = (envelope: ChatStreamCommandErrorEnvelope): void => {
        if (isDone()) {
            return;
        }
        commandErrorInFlight = commandErrorInFlight
            .then(async () => {
                await waitForQueuedStreamEvents();
                applyChatStreamCommandErrorEnvelope({ envelope, session, runtime, failProtocol, markDone, isDone });
            })
            .catch((error) => {
                failProcessing(ensureError(error));
            });
    };

    const handleCommandErrorEvent = (data: JsonValue): void => {
        const envelope = parseChatStreamCommandErrorEnvelope(data);
        if (envelope) {
            handleCommandErrorEnvelope(envelope);
        }
    };

    const applyHydratedSnapshot = (message: ChatMessage, options: { resume?: boolean | undefined; onSharedStreamState?: (() => void) | undefined; notifyUserOnTerminal?: boolean | undefined } = {}): Promise<HydratedSnapshotApplicationResult> => {
        const previousHydration = hydrationInFlight;
        const apply = async (): Promise<HydratedSnapshotApplicationResult> => {
            await previousHydration;
            await drainInFlight;
            if (isDone()) return 'terminal';
            const previousRevision = session.assistantRevision;
            let prepared = prepareAssistantSnapshot(session, message);
            if (prepared === null) {
                if (options.resume !== false) resume();
                return session.status === 'streaming' ? 'active' : 'terminal';
            }
            if (prepared.revision > 0 && previousRevision === 0) {
                await runFirstServerEventHook();
                if (isDone()) return 'terminal';
                prepared = prepareAssistantSnapshot(session, message);
                if (prepared === null) return session.status === 'streaming' ? 'active' : 'terminal';
            }
            commitAssistantSnapshot(session, prepared);
            if (prepared.revision > previousRevision) options.onSharedStreamState?.();
            const terminalEvent = prepared.message.assistantEventTimeline?.[prepared.message.assistantEventTimeline.length - 1];
            const notifyUser = options.notifyUserOnTerminal !== false;
            if (terminalEvent?.eventType === 'completed') applyCompletedStreamEvent({ session, runtime, payload: terminalEvent.payload, assistantRevision: terminalEvent.assistantRevision, failProtocol, markDone, notifyUser });
            else if (terminalEvent?.eventType === 'cancelled') applyCancelledStreamEvent({ session, runtime, payload: terminalEvent.payload, assistantRevision: terminalEvent.assistantRevision, failProtocol, markDone, notifyUser });
            else if (terminalEvent?.eventType === 'error') applyErrorStreamEvent({ session, runtime, payload: terminalEvent.payload, assistantRevision: terminalEvent.assistantRevision, failProtocol, markDone, notifyUser });
            else if (prepared.revision > previousRevision) {
                if (previousRevision === 0) await runtime.notifyCheckpoint(session, { type: 'initial-timeline' });
                else runtime.notify(session, { type: 'replay' });
            }
            if (options.resume !== false) resume();
            return session.status === 'streaming' ? 'active' : 'terminal';
        };
        const operation = apply().finally(() => {
            if (hydrationInFlight === operation) hydrationInFlight = null;
        });
        hydrationInFlight = operation;
        return operation;
    };

    const resume = (): void => {
        if (hydrationInFlight) {
            terminateHandledPromise(hydrationInFlight.then(resume, () => undefined));
            return;
        }
        if (drainInFlight) {
            const activeDrain = drainInFlight;
            terminateHandledPromise(activeDrain.then(resume, () => undefined));
            return;
        }
        paused = false;
        scheduleDrain();
    };
    return { handleStreamEvent, handleStreamEnvelope, handleCommandErrorEvent, handleCommandErrorEnvelope, waitForQueuedStreamEvents, applyHydratedSnapshot, resume };
};

export { createChatStreamEventPump };
export type { ChatStreamEventPump, SequenceMismatchDecision, SequenceMismatchPolicy };

/* SoAI - Chat feature worker request queue types [frontend/assets/ts/features/chat/messagerenderworker/workerRequestQueueTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WorkerRequest } from '@features/chat/messagerenderworker/protocol.ts';
import type { TimeoutTimer } from '@core/timers/timeoutTimer.ts';

type PendingRequest = {
    readonly workerIndex: number;
    readonly resolve: (html: string) => void;
    readonly reject: (error: Error) => void;
    abortDisposer: (() => void) | null;
    deadlineTimer: TimeoutTimer | null;
    cancelled: boolean;
};

type QueuedRequest = {
    readonly requestId: string;
    readonly payload: WorkerRequest;
    readonly resolve: (html: string) => void;
    readonly reject: (error: Error) => void;
    readonly signal: AbortSignal | null;
    abortDisposer: (() => void) | null;
};

interface ChatRenderWorkerRequestQueueDependencies {
    workerCount: number;
    requestTimeoutMs: number;
    postToWorker: (workerIndex: number, payload: WorkerRequest) => void;
    recoverWorker: (workerIndex: number, error: Error) => void;
}

export type { ChatRenderWorkerRequestQueueDependencies, PendingRequest, QueuedRequest };

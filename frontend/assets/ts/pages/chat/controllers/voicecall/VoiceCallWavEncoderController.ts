/* SoAI - Voice call WAV encoder controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallWavEncoderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isVoiceCallWavEncodeResponse, type VoiceCallWavEncodeRequest, type VoiceCallWavEncodeResponse } from '@core/media/voiceCallWavWorkerProtocol.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';

interface PendingWavEncode {
    requestId: number;
    deferred: Deferred<Blob>;
}

class VoiceCallWavEncoderController {
    readonly #workerUrl: string;
    #worker: Worker | null = null;
    #pending: PendingWavEncode | null = null;
    #requestId = 0;

    constructor(workerUrl: string) {
        this.#workerUrl = workerUrl;
    }

    encode(frames: Float32Array[], sampleRate: number): Promise<Blob> {
        this.cancel();
        const worker = this.#ensureWorker();
        const requestId = this.#requestId + 1;
        this.#requestId = requestId;
        const payload: VoiceCallWavEncodeRequest = { type: 'encode', requestId, frames, sampleRate };
        const transfer: Transferable[] = [];
        for (const frame of frames) {
            if (frame.buffer instanceof ArrayBuffer) {
                transfer.push(frame.buffer);
            }
        }
        const deferred = createDeferred<Blob>();
        this.#pending = { requestId, deferred };
        try {
            worker.postMessage(payload, transfer);
        } catch (error) {
            this.#pending = null;
            deferred.reject(ensureError(error));
        }
        return deferred.promise;
    }

    cancel(): void {
        const pending = this.#pending;
        this.#pending = null;
        if (pending) {
            pending.deferred.reject(new Error('Voice call WAV encoding cancelled'));
        }
    }

    dispose(): void {
        this.cancel();
        const worker = this.#worker;
        this.#worker = null;
        if (worker) {
            worker.onmessage = null;
            worker.onerror = null;
            worker.terminate();
        }
    }

    #ensureWorker(): Worker {
        const existing = this.#worker;
        if (existing) {
            return existing;
        }
        const worker = new Worker(this.#workerUrl, { type: 'module', name: 'soai-voice-call-wav-encoder' });
        worker.onmessage = (event: MessageEvent): void => this.#handleMessage(event.data);
        worker.onerror = (): void => this.#handleError(new Error('Voice call WAV encoder worker failed'));
        this.#worker = worker;
        return worker;
    }

    #handleMessage(value: JsonValue): void {
        const message = typeof value === 'object' ? value : null;
        if (!isVoiceCallWavEncodeResponse(message)) {
            this.#handleError(new Error('Voice call WAV encoder returned an invalid response'));
            return;
        }
        this.#handleResponse(message);
    }

    #handleResponse(response: VoiceCallWavEncodeResponse): void {
        const pending = this.#pending;
        if (!pending || pending.requestId !== response.requestId) {
            return;
        }
        this.#pending = null;
        if (response.type === 'encoded') {
            pending.deferred.resolve(response.blob);
            return;
        }
        pending.deferred.reject(new Error(response.message));
    }

    #handleError(error: Error): void {
        const pending = this.#pending;
        this.#pending = null;
        if (pending) {
            pending.deferred.reject(ensureError(error));
        }
        this.dispose();
    }
}

export { VoiceCallWavEncoderController };

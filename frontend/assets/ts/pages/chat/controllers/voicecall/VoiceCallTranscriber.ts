/* SoAI - Chat page voice call transcriber [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallTranscriber.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { transcribeAudioBlob } from '@features/chat/public.ts';
import type { VoiceCallUtterance } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

class VoiceCallTranscriber {
    readonly #apiClient: ApiClient;

    constructor(apiClient: ApiClient) {
        this.#apiClient = apiClient;
    }

    async transcribe(utterance: VoiceCallUtterance, model: string, signal: AbortSignal): Promise<string> {
        return await transcribeAudioBlob({
            apiClient: this.#apiClient,
            blob: utterance.blob,
            mimeType: utterance.mimeType,
            filenameStem: 'utterance',
            model,
            signal,
            context: 'VoiceCallTranscriber'
        });
    }
}

export { VoiceCallTranscriber };

/* SoAI - Voice call speech session connection controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallSpeechSessionConnectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiAudioSpeechSessionCallbacks, OpenAiAudioSpeechSessionClient, OpenAiAudioSpeechSessionPayload } from '@core/api/endpoints/openaiWsAudioSpeechSession.ts';
import type { VoiceCallTtsSettings } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

const VoiceCallSpeechSessionConnectionController = async (settings: VoiceCallTtsSettings, callbacks: OpenAiAudioSpeechSessionCallbacks, createSession: (payload: OpenAiAudioSpeechSessionPayload, sessionCallbacks: OpenAiAudioSpeechSessionCallbacks) => Promise<OpenAiAudioSpeechSessionClient>): Promise<OpenAiAudioSpeechSessionClient> => {
    const session = await createSession(buildVoiceCallSpeechSessionPayload(settings), callbacks);
    await session.start();
    return session;
};

const buildVoiceCallSpeechSessionPayload = (settings: VoiceCallTtsSettings): OpenAiAudioSpeechSessionPayload => {
    if (settings.voice) {
        return { model: settings.model, voice: settings.voice, responseFormat: 'wav', speed: settings.speed };
    }
    return { model: settings.model, responseFormat: 'wav', speed: settings.speed };
};

export { VoiceCallSpeechSessionConnectionController };

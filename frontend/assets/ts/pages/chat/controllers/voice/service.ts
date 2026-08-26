/* SoAI - Chat page voice service [frontend/assets/ts/pages/chat/controllers/voice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { ChatUiParameters } from '@core/types/chatParameters.ts';

interface VoiceTtsSettings {
    model: string;
    voice: string | null;
    speed: number;
}

interface VoiceSttSettings {
    model: string;
}

const resolveVoiceTtsSettings = (parameters: ChatUiParameters): VoiceTtsSettings => {
    const modelValue = parameters.voiceTtsModel;
    const model = isString(modelValue) && modelValue.trim() ? modelValue.trim() : 'auto';

    const speedValue = parameters.voiceTtsSpeed;
    const speed = isNumber(speedValue) && Number.isFinite(speedValue) && speedValue > 0 ? speedValue : 1;
    const voiceValue = parameters.voiceTtsVoice;
    const voice = optionalTrimmedString(voiceValue);

    return { model, voice, speed };
};

const resolveVoiceSttSettings = (parameters: ChatUiParameters): VoiceSttSettings => {
    const modelValue = parameters.voiceSttModel;
    const model = isString(modelValue) && modelValue.trim() ? modelValue.trim() : 'auto';
    return { model };
};

export type { VoiceSttSettings, VoiceTtsSettings };
export { resolveVoiceSttSettings, resolveVoiceTtsSettings };

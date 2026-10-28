/* SoAI - Chat feature speech failure presentation [frontend/assets/ts/features/chat/tts/speechFailurePresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readApiErrorMetadataPath } from '@core/api/errorPayloads.ts';
import { APIError } from '@core/apiError.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { i18n } from '@core/i18n/index.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';

const isTextToSpeechModelUnavailable = <T>(failure: T): failure is T & APIError => failure instanceof APIError && failure.code === 'text_to_speech_model_unavailable';

const notifyTextToSpeechSetupFailure = <T>(failure: T): boolean => isTextToSpeechModelUnavailable(failure) && notifyHandledOperationError(failure);

const resolveSpeechFailureMessage = <T>(failure: T, fallbackMessage: string): string => {
    if (isTextToSpeechModelUnavailable(failure)) return resolveOperationCauseMessage(failure.code ?? null, failure) ?? fallbackMessage;
    const parameterName = readApiErrorMetadataPath(failure, ['payload', 'error', 'param']) ?? readApiErrorMetadataPath(failure, ['payload', 'param']);
    switch (parameterName) {
        case 'voice':
            return i18n.t('chat.message.speak.invalidVoice');
        case 'response_format':
            return i18n.t('chat.message.speak.invalidResponseFormat');
        case 'speed':
            return i18n.t('chat.message.speak.invalidSpeed');
        default:
            return fallbackMessage;
    }
};

export { notifyTextToSpeechSetupFailure, resolveSpeechFailureMessage };

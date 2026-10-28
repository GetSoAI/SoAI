/* SoAI - Structured speech setup error decoding [frontend/assets/ts/core/speechsetup/failure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { SpeechSetupCandidate, SpeechSetupReason } from '@core/speechsetup/protocols.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { speechSetupReasonMessage } from '@core/speechsetup/presentation.ts';

interface SpeechSetupFailure {
    reason: SpeechSetupReason;
    candidates: readonly SpeechSetupCandidate[];
    selector: string;
    model: string;
}

const readSpeechSetupReason = <Value>(value: Value): SpeechSetupReason | null => {
    switch (value) {
        case 'no_stt_plugin':
            return 'no_stt_plugin';
        case 'backend_not_installed':
            return 'backend_not_installed';
        case 'plugin_disabled':
            return 'plugin_disabled';
        case 'no_model_installed':
            return 'no_model_installed';
        case 'model_disabled':
            return 'model_disabled';
        case 'configured_model_missing':
            return 'configured_model_missing';
        case 'not_local':
            return 'not_local';
        case 'translation_unsupported':
            return 'translation_unsupported';
        case 'unsupported_option':
            return 'unsupported_option';
        default:
            return null;
    }
};

const decodeCandidate = (value: JsonValue): SpeechSetupCandidate => {
    const record = requireRecord(value, 'Speech setup candidate');
    return {
        pluginName: readRequiredTrimmedStringValue(record['plugin_name'], 'Speech setup candidate.plugin_name'),
        displayName: readRequiredTrimmedStringValue(record['display_name'], 'Speech setup candidate.display_name'),
        state: readRequiredTrimmedStringValue(record['state'], 'Speech setup candidate.state'),
        backendInstallable: readRequiredBooleanValue(record['backend_installable'], 'Speech setup candidate.backend_installable'),
        modelsDownloadable: readRequiredBooleanValue(record['models_downloadable'], 'Speech setup candidate.models_downloadable'),
        enableRequired: readRequiredBooleanValue(record['enable_required'], 'Speech setup candidate.enable_required')
    };
};

const readSpeechSetupFailure = (value: JsonValue | undefined): SpeechSetupFailure | null => {
    if (!isJsonObject(value)) return null;
    const error = isJsonObject(value['error']) ? value['error'] : value;
    const payload = isJsonObject(error['data']) ? error['data'] : error;
    if (payload['code'] !== 'transcription_model_unavailable' && payload['code'] !== 'transcription_option_unsupported') return null;
    const details = isJsonObject(payload['details']) ? payload['details'] : null;
    const reason = readSpeechSetupReason(details?.['reason']);
    if (details === null || reason === null) return null;
    const setup = details['setup'];
    if (setup !== undefined && !Array.isArray(setup)) throw new TypeError('Speech setup candidates must be an array');
    return { reason, candidates: setup?.map(decodeCandidate) ?? [], selector: typeof details['selector'] === 'string' ? details['selector'] : '', model: typeof details['model'] === 'string' ? details['model'] : '' };
};

const renderSpeechSetupFailure = (record: JsonObject): TrustedHtml | null => {
    const failure = readSpeechSetupFailure(record);
    if (failure === null) return null;
    const setup = failure.candidates.map((candidate) => ({ 'plugin_name': candidate.pluginName, 'display_name': candidate.displayName, state: candidate.state, 'backend_installable': candidate.backendInstallable, 'models_downloadable': candidate.modelsDownloadable, 'enable_required': candidate.enableRequired }));
    const publicFailure: JsonObject = { code: 'transcription_model_unavailable', details: { reason: failure.reason, selector: failure.selector, model: failure.model, setup } };
    return uiHtml`<div class="speech-setup-note" data-speech-setup="failure" data-speech-setup-error="${uiAttr(stableJsonStringify(publicFailure))}" role="status"><p class="speech-setup-note__status speech-setup-note__status--warning"><span>${speechSetupReasonMessage(failure.reason)}</span></p></div>`;
};

export { readSpeechSetupFailure, readSpeechSetupReason, renderSpeechSetupFailure };
export type { SpeechSetupFailure };

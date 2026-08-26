/* SoAI - Shared chat parameter send-toggle state transitions [frontend/assets/ts/core/chat/parameters/parameterSendToggleState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PARAMETER_SEND_CONTROLS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const restoreDisabledParameterSendValues = (parameters: ChatParameters, baseline: ChatParameters, changedParameter: string, changedValue: JsonValue): readonly string[] => {
    if (changedValue !== false) return [];
    const restoredParameters: string[] = [];
    for (const sendControl of CHAT_PARAMETER_SEND_CONTROLS) {
        if (sendControl.flag !== changedParameter) continue;
        parameters[sendControl.parameter] = baseline[sendControl.parameter];
        restoredParameters.push(sendControl.parameter);
    }
    return restoredParameters;
};

export { restoreDisabledParameterSendValues };

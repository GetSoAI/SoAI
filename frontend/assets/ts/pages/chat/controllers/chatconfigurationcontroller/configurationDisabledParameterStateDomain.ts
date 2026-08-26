/* SoAI - Restored disabled chat configuration parameter values [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/configurationDisabledParameterStateDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { restoreDisabledParameterSendValues } from '@core/chat/parameters/parameterSendToggleState.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatParameters } from '@features/chat/public.ts';

const resolveRestoredDisabledParameterValues = (inputArguments: { parameters: ChatParameters | null; baseline: ChatParameters | null; parameter: string; value: JsonValue }): readonly string[] => {
    if (!inputArguments.parameters || !inputArguments.baseline || inputArguments.value !== false) {
        return [];
    }
    return restoreDisabledParameterSendValues(inputArguments.parameters, inputArguments.baseline, inputArguments.parameter, inputArguments.value);
};

export { resolveRestoredDisabledParameterValues };

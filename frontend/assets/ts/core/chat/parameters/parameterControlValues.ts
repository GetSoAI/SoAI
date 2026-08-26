/* SoAI - Canonical chat request parameter control values [frontend/assets/ts/core/chat/parameters/parameterControlValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { splitTrimmedList } from '@core/normalize.ts';
import { normalizeNumericParameter } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_WIRE_TO_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ChatParameterControlValue {
    parameter: string;
    value: JsonValue;
}

type ChatParameterControlReadResult = ChatParameterControlValue | 'invalid' | null;

const NULLABLE_NUMERIC_PARAMETERS = new Set(['contextWindowTokens', 'maxCompletionTokens', 'topLogprobs']);

const resolveChatParameterKey = (domParameter: string): string => CHAT_WIRE_TO_PARAMETER_KEYS[domParameter] ?? domParameter;

const readChatParameterControlValue = (element: Element, domParameter: string | null): ChatParameterControlReadResult => {
    if (!domParameter) return null;
    if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLSelectElement)) {
        throw new TypeError('Chat parameter element must be an HTMLInputElement, HTMLTextAreaElement, or HTMLSelectElement');
    }
    const parameter = resolveChatParameterKey(domParameter);
    let value: JsonValue;
    if (element instanceof HTMLSelectElement) {
        value = element.value === '' ? null : element.value;
    } else if (element instanceof HTMLTextAreaElement) {
        value = element.value;
    } else if (element.type === 'checkbox') {
        value = element.checked;
    } else if (parameter === 'stop') {
        value = splitTrimmedList(element.value, ',');
    } else if (element.type === 'number' && !element.validity.valid) {
        return 'invalid';
    } else if (readTrimmedInputValue(element) === '' && NULLABLE_NUMERIC_PARAMETERS.has(parameter)) {
        value = null;
    } else {
        value = normalizeNumericParameter(parameter, element.value);
    }
    return { parameter, value };
};

export { readChatParameterControlValue, resolveChatParameterKey };
export type { ChatParameterControlReadResult, ChatParameterControlValue };

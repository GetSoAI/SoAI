/* SoAI - Shared OpenAI model test stream parsing [frontend/assets/ts/core/openai/modelTestStreamParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const readInnerPayload = (payload: JsonValue): JsonObject | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const innerPayload = payload['payload'];
    return isJsonObject(innerPayload) ? innerPayload : null;
};

const readModelTestRunId = (payload: JsonValue): string | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const runIdValue = payload['run_id'];
    if (!isString(runIdValue)) {
        return null;
    }
    const trimmed = runIdValue.trim();
    return trimmed ? trimmed : null;
};

const readModelTestSequence = (payload: JsonValue): number | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const sequenceValue = payload['sequence'];
    return isNumber(sequenceValue) && Number.isInteger(sequenceValue) ? sequenceValue : null;
};

const readModelTestEventType = (payload: JsonValue): string | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const eventTypeValue = payload['event_type'];
    if (!isString(eventTypeValue)) {
        return null;
    }
    const normalized = eventTypeValue.trim();
    return normalized ? normalized : null;
};

const readModelTestDeltaText = (payload: JsonValue): string => {
    const innerPayload = readInnerPayload(payload);
    if (innerPayload === null) {
        return '';
    }
    const deltaValue = innerPayload['delta'];
    return isString(deltaValue) ? deltaValue : '';
};

const readModelTestErrorMessage = (payload: JsonValue): string | null => {
    const innerPayload = readInnerPayload(payload);
    if (innerPayload === null) {
        return null;
    }
    const messageValue = innerPayload['message'];
    if (!isString(messageValue)) {
        return null;
    }
    const normalized = messageValue.trim();
    return normalized ? normalized : null;
};

export { readModelTestDeltaText, readModelTestErrorMessage, readModelTestEventType, readModelTestRunId, readModelTestSequence };

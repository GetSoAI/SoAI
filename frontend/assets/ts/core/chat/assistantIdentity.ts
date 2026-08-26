/* SoAI - Assistant message identity validation primitives [frontend/assets/ts/core/chat/assistantIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isNumber, isPositiveInteger } from '@core/typeGuards.ts';

type AssistantVariantIdentity = {
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type AssistantMessageIdentity = AssistantVariantIdentity & {
    assistantTimestamp: number;
};

const isPositiveEpochMs = (value: JsonValue | null | undefined): value is number => {
    return isNumber(value) && isEpochMsNumber(value) && value > 0;
};

const resolvePositiveAssistantRevision = (value: JsonValue | null | undefined): number | null => {
    return isPositiveInteger(value) ? value : null;
};

const requirePositiveEpochMs = (value: JsonValue | null | undefined, label: string): number => {
    if (!isPositiveEpochMs(value)) {
        throw new Error(`${label} must be a positive epoch millisecond integer`);
    }
    return value;
};

const requireNonNegativeModelVariantIndex = (value: JsonValue | null | undefined, label: string): number => {
    if (!isNonNegativeInteger(value)) {
        throw new Error(`${label} must be a non-negative integer`);
    }
    return value;
};

const requireAssistantVariantIdentity = (inputArguments: { assistantTurnTimestamp: JsonValue | null | undefined; modelVariantIndex: JsonValue | null | undefined; context: string }): AssistantVariantIdentity => {
    return {
        assistantTurnTimestamp: requirePositiveEpochMs(inputArguments.assistantTurnTimestamp, `${inputArguments.context} assistant_turn_at_ms`),
        modelVariantIndex: requireNonNegativeModelVariantIndex(inputArguments.modelVariantIndex, `${inputArguments.context} model_variant_index`)
    };
};

const requireAssistantMessageIdentity = (inputArguments: { assistantTimestamp: JsonValue | null | undefined; assistantTurnTimestamp: JsonValue | null | undefined; modelVariantIndex: JsonValue | null | undefined; context: string }): AssistantMessageIdentity => {
    const assistantTimestamp = requirePositiveEpochMs(inputArguments.assistantTimestamp, `${inputArguments.context} timestamp`);
    const identity = requireAssistantVariantIdentity({
        assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
        modelVariantIndex: inputArguments.modelVariantIndex,
        context: inputArguments.context
    });
    if (identity.assistantTurnTimestamp > assistantTimestamp) {
        throw new Error(`${inputArguments.context} assistant_turn_at_ms must not be greater than timestamp`);
    }
    if (identity.modelVariantIndex === 0 && identity.assistantTurnTimestamp !== assistantTimestamp) {
        throw new Error(`${inputArguments.context} canonical variant timestamp must equal assistant_turn_at_ms`);
    }
    return {
        assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex
    };
};

const resolveAssistantVariantIdentity = (inputArguments: { assistantTurnTimestamp: JsonValue | null | undefined; modelVariantIndex: JsonValue | null | undefined }): AssistantVariantIdentity | null => {
    if (!isPositiveEpochMs(inputArguments.assistantTurnTimestamp) || !isNonNegativeInteger(inputArguments.modelVariantIndex)) {
        return null;
    }
    return {
        assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
        modelVariantIndex: inputArguments.modelVariantIndex
    };
};

const resolveAssistantMessageIdentity = (inputArguments: { assistantTimestamp: JsonValue | null | undefined; assistantTurnTimestamp: JsonValue | null | undefined; modelVariantIndex: JsonValue | null | undefined }): AssistantMessageIdentity | null => {
    if (!isPositiveEpochMs(inputArguments.assistantTimestamp)) {
        return null;
    }
    const identity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
        modelVariantIndex: inputArguments.modelVariantIndex
    });
    if (!identity) {
        return null;
    }
    if (identity.assistantTurnTimestamp > inputArguments.assistantTimestamp) {
        return null;
    }
    if (identity.modelVariantIndex === 0 && identity.assistantTurnTimestamp !== inputArguments.assistantTimestamp) {
        return null;
    }
    return {
        assistantTimestamp: inputArguments.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex
    };
};

export { requireAssistantMessageIdentity, requireAssistantVariantIdentity, requireNonNegativeModelVariantIndex, requirePositiveEpochMs, resolveAssistantMessageIdentity, resolveAssistantVariantIdentity, resolvePositiveAssistantRevision };
export type { AssistantMessageIdentity, AssistantVariantIdentity };

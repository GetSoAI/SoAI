/* SoAI - Chat identity-prompt settings snapshot state [frontend/assets/ts/features/chat/conversationsettings/identitypromptsconversationsettingscontroller/identityPromptsSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';

type IdentityPromptsSnapshot = {
    userDisplayName: string | null;
    assistantDisplayName: string | null;
    userSystemPrompt: string | null;
    userSystemPromptLockEnabled: boolean;
    soaiSystemPromptEnabled: boolean;
};

const normalizeOptionalBool = (value: JsonValue | undefined, defaultValue: boolean): boolean => {
    if (isBoolean(value)) {
        return value;
    }
    if (typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value)) {
        if (value === 0) return false;
        if (value === 1) return true;
    }
    if (isString(value)) {
        const normalized = value.trim().toLowerCase();
        if (normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'on' || normalized === 'enabled') {
            return true;
        }
        if (normalized === 'false' || normalized === '0' || normalized === 'no' || normalized === 'off' || normalized === 'disabled') {
            return false;
        }
    }
    return defaultValue;
};

const snapshotsEqual = (firstValue: IdentityPromptsSnapshot | null, secondValue: IdentityPromptsSnapshot | null): boolean => {
    if (!firstValue || !secondValue) {
        return false;
    }
    return firstValue.userDisplayName === secondValue.userDisplayName && firstValue.assistantDisplayName === secondValue.assistantDisplayName && firstValue.userSystemPrompt === secondValue.userSystemPrompt && firstValue.userSystemPromptLockEnabled === secondValue.userSystemPromptLockEnabled && firstValue.soaiSystemPromptEnabled === secondValue.soaiSystemPromptEnabled;
};

const resolveIdentityPromptsFromConversation = (conversation: ConversationContract | null, userSystemPromptLockEnabled: boolean): IdentityPromptsSnapshot => {
    const modelSettingsValue = conversation ? conversation.modelSettings : null;
    const identity = modelSettingsValue?.identity;
    const prompts = modelSettingsValue?.prompts;
    return {
        userDisplayName: toTrimmedStringOrNull(identity?.userDisplayName),
        assistantDisplayName: toTrimmedStringOrNull(identity?.assistantDisplayName),
        userSystemPrompt: toTrimmedStringOrNull(prompts?.userSystemPrompt),
        userSystemPromptLockEnabled: userSystemPromptLockEnabled,
        soaiSystemPromptEnabled: normalizeOptionalBool(prompts?.soaiSystemPromptEnabled, true)
    };
};

export { resolveIdentityPromptsFromConversation, snapshotsEqual };
export type { IdentityPromptsSnapshot };

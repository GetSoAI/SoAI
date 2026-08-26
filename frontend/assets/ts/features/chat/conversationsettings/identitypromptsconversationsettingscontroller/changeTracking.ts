/* SoAI - Identity prompt change tracking for conversation settings [frontend/assets/ts/features/chat/conversationsettings/identitypromptsconversationsettingscontroller/changeTracking.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireFieldSurface } from '@core/forms/fieldSurface.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { IdentityPromptsSnapshot } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/identityPromptsSnapshot.ts';
import { readIdentityPromptsSnapshotFromForm } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/snapshotBindings.ts';

const IDENTITY_PROMPT_SETTING_KEYS = Object.freeze(['identity.user_display_name', 'identity.assistant_display_name', 'prompts.user_system_prompt', 'prompts.user_system_prompt_lock_enabled', 'prompts.soai_system_prompt_enabled']);

const readSnapshotValue = (snapshot: IdentityPromptsSnapshot | null, key: string): JsonValue => {
    if (!snapshot) {
        return null;
    }
    if (key === 'identity.user_display_name') {
        return snapshot.userDisplayName;
    }
    if (key === 'identity.assistant_display_name') {
        return snapshot.assistantDisplayName;
    }
    if (key === 'prompts.user_system_prompt') {
        return snapshot.userSystemPrompt;
    }
    if (key === 'prompts.user_system_prompt_lock_enabled') {
        return snapshot.userSystemPromptLockEnabled;
    }
    if (key === 'prompts.soai_system_prompt_enabled') {
        return snapshot.soaiSystemPromptEnabled;
    }
    return null;
};

const createIdentityPromptsChangeTracker = (options: { modal: Element; getBaseline: () => IdentityPromptsSnapshot | null }): FieldStateTracker => {
    return new FieldStateTracker({
        getElement: (key: string) => {
            const element = dom.resolve(`[data-setting="${key}"]`, options.modal);
            return element ? requireFieldSurface(element) : null;
        },
        getCurrentValue: (key: string) => readSnapshotValue(readIdentityPromptsSnapshotFromForm(options.modal), key),
        getOriginalValue: (key: string) => readSnapshotValue(options.getBaseline(), key)
    });
};

const syncIdentityPromptsChangeTracker = (tracker: FieldStateTracker | null, baseline: IdentityPromptsSnapshot | null): void => {
    if (!tracker || !baseline) {
        tracker?.clearAll();
        return;
    }
    tracker.refresh([...IDENTITY_PROMPT_SETTING_KEYS]);
};

export { createIdentityPromptsChangeTracker, syncIdentityPromptsChangeTracker };

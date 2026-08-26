/* SoAI - Chat feature snapshot bindings [frontend/assets/ts/features/chat/conversationsettings/identitypromptsconversationsettingscontroller/snapshotBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { IdentityPromptsSnapshot } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/identityPromptsSnapshot.ts';

const applyIdentityPromptsSnapshotToConversation = (conversation: ConversationContract, snapshot: IdentityPromptsSnapshot): void => {
    const modelSettingsValue = conversation.modelSettings;
    const modelSettings = modelSettingsValue ?? { model: null };
    modelSettings.identity = {
        ...modelSettings.identity,
        userDisplayName: snapshot.userDisplayName,
        assistantDisplayName: snapshot.assistantDisplayName
    };
    modelSettings.prompts = {
        ...modelSettings.prompts,
        userSystemPrompt: snapshot.userSystemPrompt,
        soaiSystemPromptEnabled: snapshot.soaiSystemPromptEnabled
    };
    conversation.modelSettings = modelSettings;
};

const applyIdentityPromptsSnapshotToForm = (host: ConversationSettingsHost, modal: Element, snapshot: IdentityPromptsSnapshot): void => {
    const setText = (path: string, value: string | null): void => {
        const element = dom.resolve(`[data-setting="${path}"]`, modal);
        if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) {
            return;
        }
        const next = value ? value : '';
        host.view.setUIValue(element, next, { attribute: 'value' });
    };
    setText('identity.user_display_name', snapshot.userDisplayName);
    setText('identity.assistant_display_name', snapshot.assistantDisplayName);
    setText('prompts.user_system_prompt', snapshot.userSystemPrompt);

    const lockCheckbox = dom.resolve('[data-setting="prompts.user_system_prompt_lock_enabled"]', modal);
    if (lockCheckbox instanceof HTMLInputElement && lockCheckbox.type === 'checkbox') {
        host.view.updateProperty(lockCheckbox, 'checked', snapshot.userSystemPromptLockEnabled);
        updateToggleLabel(lockCheckbox, { checked: snapshot.userSystemPromptLockEnabled });
    }

    const checkbox = dom.resolve('[data-setting="prompts.soai_system_prompt_enabled"]', modal);
    if (checkbox instanceof HTMLInputElement && checkbox.type === 'checkbox') {
        host.view.updateProperty(checkbox, 'checked', snapshot.soaiSystemPromptEnabled);
        updateToggleLabel(checkbox, { checked: snapshot.soaiSystemPromptEnabled });
    }
};

const readIdentityPromptsSnapshotFromForm = (modal: Element | null): IdentityPromptsSnapshot => {
    const readText = (path: string): string | null => {
        if (!modal) {
            return null;
        }
        const element = dom.resolve(`[data-setting="${path}"]`, modal);
        if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
            return toTrimmedStringOrNull(element.value);
        }
        return null;
    };
    const readBool = (path: string, defaultValue: boolean): boolean => {
        if (!modal) {
            return defaultValue;
        }
        const element = dom.resolve(`[data-setting="${path}"]`, modal);
        if (element instanceof HTMLInputElement && element.type === 'checkbox') {
            return element.checked;
        }
        return defaultValue;
    };
    return {
        userDisplayName: readText('identity.user_display_name'),
        assistantDisplayName: readText('identity.assistant_display_name'),
        userSystemPrompt: readText('prompts.user_system_prompt'),
        userSystemPromptLockEnabled: readBool('prompts.user_system_prompt_lock_enabled', false),
        soaiSystemPromptEnabled: readBool('prompts.soai_system_prompt_enabled', true)
    };
};

export { applyIdentityPromptsSnapshotToConversation, applyIdentityPromptsSnapshotToForm, readIdentityPromptsSnapshotFromForm };

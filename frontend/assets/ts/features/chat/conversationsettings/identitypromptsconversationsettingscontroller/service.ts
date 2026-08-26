/* SoAI - Chat feature identity prompts conversation settings controller service [frontend/assets/ts/features/chat/conversationsettings/identitypromptsconversationsettingscontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isUnicodeScalarText } from '@core/primitives/text.ts';
import { i18n } from '@core/i18n/index.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { readUserSystemPromptLockState, writeUserSystemPromptLockState } from '@features/chat/systemPromptLock.ts';
import { resolveIdentityPromptsFromConversation, snapshotsEqual, type IdentityPromptsSnapshot } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/identityPromptsSnapshot.ts';
import { applyIdentityPromptsSnapshotToForm, readIdentityPromptsSnapshotFromForm } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/snapshotBindings.ts';
import { createIdentityPromptsChangeTracker, syncIdentityPromptsChangeTracker } from '@features/chat/conversationsettings/identitypromptsconversationsettingscontroller/changeTracking.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

class IdentityPromptsConversationSettingsController {
    readonly #host: ConversationSettingsHost;
    #modal: Element | null = null;
    #baseline: IdentityPromptsSnapshot | null = null;
    #working: IdentityPromptsSnapshot | null = null;
    #settingChangeTracker: FieldStateTracker | null = null;
    #dirtyCallback: ((hasChanges: boolean) => void) | null = null;
    readonly #handleSettingInput = (event: Event): void => {
        this.#handleSettingEvent(event);
    };
    readonly #handleSettingChange = (event: Event): void => {
        this.#handleSettingEvent(event);
    };

    constructor(options: { host: ConversationSettingsHost; onDirtyStateChange: (hasChanges: boolean) => void }) {
        this.#host = options.host;
        this.#dirtyCallback = options.onDirtyStateChange;
    }

    bindEvents(modal: Element): Array<() => void> {
        this.#modal = modal;
        this.#settingChangeTracker = createIdentityPromptsChangeTracker({ modal, getBaseline: () => this.#baseline });
        const abortController = new AbortController();
        const { signal } = abortController;

        modal.addEventListener('input', this.#handleSettingInput, { signal });
        modal.addEventListener('change', this.#handleSettingChange, { signal });

        return [
            () => {
                abortController.abort();
            }
        ];
    }

    resetUI(): void {
        this.#baseline = null;
        this.#working = null;
        this.#settingChangeTracker?.clearAll();
        this.#dirtyCallback?.(false);
    }

    dispose(): void {
        this.#settingChangeTracker?.clearAll();
        this.#settingChangeTracker = null;
        this.#modal = null;
        this.resetUI();
        this.#dirtyCallback = null;
    }

    syncFromConversation(conversation: ConversationContract | null): void {
        if (!this.#modal) {
            return;
        }
        const lockState = readUserSystemPromptLockState(this.#host.data.storage.getChatPreferences());
        const snapshot = resolveIdentityPromptsFromConversation(conversation, lockState.enabled);
        this.#baseline = snapshot;
        this.#working = { ...snapshot };
        applyIdentityPromptsSnapshotToForm(this.#host, this.#modal, snapshot);
        this.#dirtyCallback?.(false);
        syncIdentityPromptsChangeTracker(this.#settingChangeTracker, this.#baseline);
    }

    isHydrated(): boolean {
        return this.#baseline !== null && this.#working !== null;
    }

    isValid(): boolean {
        const working = this.#working;
        if (!working || !this.#settingChangeTracker?.isValid()) {
            return false;
        }
        return [working.userDisplayName, working.assistantDisplayName].every((value) => value === null || (isUnicodeScalarText(value) && Array.from(value).length <= 50)) && (working.userSystemPrompt === null || isUnicodeScalarText(working.userSystemPrompt));
    }

    workingSnapshot(): IdentityPromptsSnapshot | null {
        return this.#working ? { ...this.#working } : null;
    }

    baselineSnapshot(): IdentityPromptsSnapshot | null {
        return this.#baseline ? { ...this.#baseline } : null;
    }

    mergePresetSections(general: JsonObject | undefined, completion: JsonObject | undefined): IdentityPromptsSnapshot | null {
        if (!this.#working) {
            return null;
        }
        const next = { ...this.#working };
        const assignNullableString = (record: JsonObject | undefined, key: string, assign: (value: string | null) => void): boolean => {
            if (!record || !(key in record)) return true;
            const value = record[key];
            if (value !== null && typeof value !== 'string') return false;
            assign(value);
            return true;
        };
        const assignBoolean = (record: JsonObject | undefined, key: string, assign: (value: boolean) => void): boolean => {
            if (!record || !(key in record)) return true;
            const value = record[key];
            if (typeof value !== 'boolean') return false;
            assign(value);
            return true;
        };
        const valid =
            assignNullableString(general, 'user_display_name', (value) => {
                next.userDisplayName = value;
            }) &&
            assignNullableString(general, 'assistant_display_name', (value) => {
                next.assistantDisplayName = value;
            }) &&
            assignNullableString(completion, 'user_system_prompt', (value) => {
                next.userSystemPrompt = value;
            }) &&
            assignBoolean(completion, 'user_system_prompt_lock_enabled', (value) => {
                next.userSystemPromptLockEnabled = value;
            }) &&
            assignBoolean(completion, 'soai_system_prompt_enabled', (value) => {
                next.soaiSystemPromptEnabled = value;
            });
        if (!valid || ![next.userDisplayName, next.assistantDisplayName].every((value) => value === null || (isUnicodeScalarText(value) && Array.from(value).length <= 50))) return null;
        return next;
    }

    commitWorkingSnapshot(snapshot: IdentityPromptsSnapshot): void {
        this.#working = { ...snapshot };
    }

    refreshWorkingPresentation(): void {
        if (!this.#modal || !this.#working) {
            return;
        }
        applyIdentityPromptsSnapshotToForm(this.#host, this.#modal, this.#working);
        this.#updateApplyState();
    }

    rebase(snapshot: IdentityPromptsSnapshot): void {
        this.#baseline = { ...snapshot };
        this.#working = { ...snapshot };
        this.refreshWorkingPresentation();
    }

    conversationPatch(): ConversationModelSettingsUpdate {
        const current = this.#working;
        const baseline = this.#baseline;
        if (!current) return {};
        const patch: ConversationModelSettingsUpdate = {};
        if (!baseline || current.userDisplayName !== baseline.userDisplayName || current.assistantDisplayName !== baseline.assistantDisplayName) {
            patch.identity = {};
            if (!baseline || current.userDisplayName !== baseline.userDisplayName) patch.identity.userDisplayName = current.userDisplayName;
            if (!baseline || current.assistantDisplayName !== baseline.assistantDisplayName) patch.identity.assistantDisplayName = current.assistantDisplayName;
        }
        if (!baseline || current.userSystemPrompt !== baseline.userSystemPrompt || current.soaiSystemPromptEnabled !== baseline.soaiSystemPromptEnabled) {
            patch.prompts = {};
            if (!baseline || current.userSystemPrompt !== baseline.userSystemPrompt) patch.prompts.userSystemPrompt = current.userSystemPrompt;
            if (!baseline || current.soaiSystemPromptEnabled !== baseline.soaiSystemPromptEnabled) patch.prompts.soaiSystemPromptEnabled = current.soaiSystemPromptEnabled;
        }
        return patch;
    }

    finalizeConversationSave(): void {
        const conversation = this.#host.data.getCurrentConversation();
        const current = this.#working;
        if (!current || !isChatConversationSettingsWritable(conversation)) return;
        const lockBaseline = this.#baseline?.userSystemPromptLockEnabled ?? current.userSystemPromptLockEnabled;
        this.#baseline = { ...current, userSystemPromptLockEnabled: lockBaseline };
        this.#working = { ...current };
        this.refreshWorkingPresentation();
        this.#host.workflow.invalidateChatMarkup('current');
        this.#host.workflow.refreshTokenCounterPreview();
        terminateHandledPromise(this.#host.workflow.renderCurrentConversation());
    }

    finalizePreferenceSave(): void {
        const current = this.#working;
        if (!current) return;
        writeUserSystemPromptLockState(this.#host.data.storage, { enabled: current.userSystemPromptLockEnabled, value: current.userSystemPrompt });
        this.rebase(current);
    }

    #handleSettingEvent(event: Event): void {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const settingTarget = target.closest('[data-setting]');
        if (!(settingTarget instanceof HTMLInputElement) && !(settingTarget instanceof HTMLTextAreaElement)) {
            return;
        }
        const setting = this.#host.view.dom.getData(settingTarget, 'setting');
        if (!setting) {
            return;
        }
        if (settingTarget instanceof HTMLInputElement && settingTarget.type === 'checkbox') {
            updateToggleLabel(settingTarget, { checked: settingTarget.checked });
        }
        this.#working = readIdentityPromptsSnapshotFromForm(this.#modal);
        this.#updateApplyState();
    }

    #updateApplyState(): void {
        const baseline = this.#baseline;
        const current = this.#working ?? readIdentityPromptsSnapshotFromForm(this.#modal);
        const hasChanges = baseline ? !snapshotsEqual(current, baseline) : true;
        this.#dirtyCallback?.(hasChanges);
        syncIdentityPromptsChangeTracker(this.#settingChangeTracker, baseline);
        const invalidName = [current.userDisplayName, current.assistantDisplayName].some((value) => value !== null && (!isUnicodeScalarText(value) || Array.from(value).length > 50));
        const nameMessage = invalidName ? i18n.t('chat.configuration.identityNameInvalid') : null;
        this.#settingChangeTracker?.setInvalid('identity.user_display_name', nameMessage);
        this.#settingChangeTracker?.setInvalid('identity.assistant_display_name', nameMessage);
        this.#settingChangeTracker?.setInvalid('prompts.user_system_prompt', current.userSystemPrompt !== null && !isUnicodeScalarText(current.userSystemPrompt) ? i18n.t('chat.configuration.promptInvalid') : null);
    }
}

export { IdentityPromptsConversationSettingsController };

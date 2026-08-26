/* SoAI - Messaging account editor form state [frontend/assets/ts/features/settings/messaging/modalFormState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAuthorizedSender, MessagingPlatform } from '@core/api/contracts/messagingAccountContracts.ts';
import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceSelectOptions, type SelectOptionDefinition } from '@core/dom/selectOptions.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { buildStoredChatParameters } from '@core/chat/parameters/chatRequestParameters.ts';
import { cloneChatParameters, type ChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { normalizeAgentMaxIterationsParameter } from '@core/chat/parameters/agentMaxIterations.ts';
import { isAgentMode, type AgentMode } from '@core/chat/agentMode.ts';
import type { ChatParameterEditorPrompts, ChatParameterEditorState } from '@core/chat/parameters/parameterEditorState.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';
import type { McpFormController } from '@core/mcp/mcpFormController.ts';
import type { WorkspacePathDraft } from '@core/fileexplorerbrowser/workspacePathDraft.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { MESSAGING_PROVIDER_DESCRIPTORS, getMessagingProviderDescriptor } from '@features/settings/messaging/descriptors.ts';
import { applyMessagingModelSelection, type MessagingCredentialDrafts, type MessagingDraft } from '@features/settings/messaging/modalDraft.ts';
import type { MessagingAccountModalOptions } from '@features/settings/messaging/types.ts';

interface MessagingEditorState {
    parameters: ChatParameters;
    prompts: ChatParameterEditorPrompts;
    initiallyExplicitSettings: boolean;
}

const requireInput = (modal: Element, token: string): HTMLInputElement => {
    const element = dom.resolve(modalUiSelector('settings-messaging-account-modal', token), modal);
    if (!(element instanceof HTMLInputElement)) throw new Error(`Messaging editor input is missing: ${token}`);
    return element;
};

const requireSelect = (modal: Element, token: string): HTMLSelectElement => {
    const element = dom.resolve(modalUiSelector('settings-messaging-account-modal', token), modal);
    if (!(element instanceof HTMLSelectElement)) throw new Error(`Messaging editor select is missing: ${token}`);
    return element;
};

const requireTextarea = (modal: Element, token: string): HTMLTextAreaElement => {
    const element = dom.resolve(modalUiSelector('settings-messaging-account-modal', token), modal);
    if (!(element instanceof HTMLTextAreaElement)) throw new Error(`Messaging editor textarea is missing: ${token}`);
    return element;
};

const populateModels = (select: HTMLSelectElement, options: MessagingAccountModalOptions, current: string | null): void => {
    const modelOptions: SelectOptionDefinition[] = options.models.map((model) => ({ value: model.executionId, label: model.displayName }));
    if (current && !options.models.some((model) => model.executionId === current)) modelOptions.unshift({ value: current, label: current });
    replaceSelectOptions(select, modelOptions);
    setSelectValueAndSyncDefault(select, current ?? modelOptions[0]?.value ?? '');
};

const createParameterEditorState = (settings: ConversationModelSettings): MessagingEditorState => {
    const parameters = cloneChatParameters(settings.parameters ?? {});
    parameters.agentMaxIterations = normalizeAgentMaxIterationsParameter(settings.agent?.maxIterations);
    return {
        parameters,
        prompts: {
            userSystemPrompt: settings.prompts?.userSystemPrompt ?? null,
            userSystemPromptLockEnabled: false,
            soaiSystemPromptEnabled: settings.prompts?.soaiSystemPromptEnabled ?? true
        },
        initiallyExplicitSettings: settings.parameters !== undefined || settings.prompts !== undefined || settings.agent?.maxIterations !== undefined
    };
};

const platformFromSelect = (modal: Element): MessagingPlatform => {
    const value = readTrimmedSelectValue(requireSelect(modal, 'platform'));
    if (value === 'telegram' || value === 'whatsapp' || value === 'discord') return value;
    throw new Error('Messaging platform is invalid');
};

const syncCredentialSections = (modal: HTMLElement): void => {
    const selected = platformFromSelect(modal);
    dom.resolveAll('.messaging-provider-credentials', modal).forEach((section) => {
        if (!(section instanceof HTMLElement)) throw new Error('Messaging credential section must be an HTML element');
        section.hidden = section.dataset['platform'] !== selected;
    });
    const replaceCallbackItem = dom.resolve(modalUiSelector('settings-messaging-account-modal', 'replace-callback-item'), modal);
    if (!(replaceCallbackItem instanceof HTMLElement)) throw new Error('Messaging callback replacement setting is missing');
    replaceCallbackItem.hidden = selected === 'discord';
};

const syncSenderAccessState = (modal: HTMLElement): void => {
    const acceptAnyone = requireInput(modal, 'accept-anyone').checked;
    const authorizedSenders = requireTextarea(modal, 'authorized-senders');
    authorizedSenders.disabled = acceptAnyone;
    authorizedSenders.setAttribute('aria-disabled', String(acceptAnyone));
};

const initializeMessagingEditor = (modal: HTMLElement, options: MessagingAccountModalOptions): MessagingEditorState => {
    const account = options.account;
    const platform = account?.platform ?? 'telegram';
    requireInput(modal, 'label').value = account?.label ?? '';
    const platformSelect = requireSelect(modal, 'platform');
    platformSelect.value = platform;
    platformSelect.disabled = options.mode === 'edit';
    requireSelect(modal, 'locale').value = account?.locale ?? 'en';
    requireInput(modal, 'plaintext-secrets').checked = account?.plaintextSecretRepliesEnabled ?? false;
    requireInput(modal, 'accept-anyone').checked = account?.acceptMessagesFromAnyone ?? false;
    requireInput(modal, 'replace-callback').checked = false;
    requireTextarea(modal, 'authorized-senders').value = (account?.authorizedSenders ?? []).map((sender) => (sender.displayLabel ? `${sender.senderId} | ${sender.displayLabel}` : sender.senderId)).join('\n');
    for (const descriptor of MESSAGING_PROVIDER_DESCRIPTORS) {
        for (const field of descriptor.fields) {
            const input = requireInput(modal, `credential-${descriptor.id}-${field.uiToken}`);
            input.value = field.defaultValue;
            if (options.mode === 'edit' && field.inputType === 'password') input.placeholder = '••••••••';
        }
    }
    const settings = account?.modelSettings ?? { model: options.models[0]?.executionId ?? null };
    const modelSelect = requireSelect(modal, 'model');
    populateModels(modelSelect, options, settings.model);
    const agentMode = settings.agent?.mode ?? 'chat';
    requireSelect(modal, 'agent-mode').value = agentMode;
    requireInput(modal, 'user-name').value = settings.identity?.userDisplayName ?? '';
    requireInput(modal, 'assistant-name').value = settings.identity?.assistantDisplayName ?? '';
    syncCredentialSections(modal);
    syncSenderAccessState(modal);
    const state = createParameterEditorState(settings);
    const initialDraft = readMessagingDraft(modal, options, state, null, null);
    applyMessagingModelSelection(initialDraft, options.models, readTrimmedSelectValue(modelSelect), 'initialize');
    state.parameters.contextWindowTokens = initialDraft.modelSettings.parameters?.contextWindowTokens ?? null;
    return state;
};

const applyMessagingModelChange = (modal: HTMLElement, options: MessagingAccountModalOptions, state: MessagingEditorState, mcp: McpFormController, workspace: WorkspacePathDraft): void => {
    const draft = readMessagingDraft(modal, options, state, mcp, workspace);
    applyMessagingModelSelection(draft, options.models, readTrimmedSelectValue(requireSelect(modal, 'model')), 'user');
    const parameters = draft.modelSettings.parameters ?? {};
    state.parameters.contextWindowTokens = parameters.contextWindowTokens ?? null;
    state.parameters.maxCompletionTokens = parameters.maxCompletionTokens ?? null;
};

const applyMessagingParameterEditorState = (state: MessagingEditorState, edited: ChatParameterEditorState): void => {
    state.parameters = edited.parameters;
    state.prompts = edited.prompts;
};

const readCredential = (modal: Element, platform: MessagingPlatform, key: string): string => {
    const descriptor = getMessagingProviderDescriptor(platform);
    const field = descriptor.fields.find((candidate) => candidate.key === key);
    if (!field) throw new Error('Messaging credential field is invalid');
    return readTrimmedInputValue(requireInput(modal, `credential-${platform}-${field.uiToken}`));
};

const readAuthorizedSenders = (value: string): MessagingAuthorizedSender[] => {
    return value
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
            const separator = line.indexOf('|');
            const senderId = (separator < 0 ? line : line.slice(0, separator)).trim();
            const label = separator < 0 ? null : line.slice(separator + 1).trim() || null;
            return { senderId, displayLabel: label };
        });
};

const buildSettings = (modal: HTMLElement, state: MessagingEditorState, mcp: McpFormController, workspace: WorkspacePathDraft, existing: ConversationModelSettings | null): ConversationModelSettings => {
    const modeValue = readTrimmedSelectValue(requireSelect(modal, 'agent-mode'));
    if (!isAgentMode(modeValue)) throw new Error('mode');
    const mode: AgentMode = modeValue;
    const settings: ConversationModelSettings = {
        ...(existing?.additionalSettings ? { additionalSettings: existing.additionalSettings } : {}),
        model: readTrimmedSelectValue(requireSelect(modal, 'model')) || null,
        parameters: { ...(existing?.parameters?.additionalParameters ? { additionalParameters: existing.parameters.additionalParameters } : {}), ...buildStoredChatParameters(state.parameters) },
        agent: { ...(existing?.agent?.additionalSettings ? { additionalSettings: existing.agent.additionalSettings } : {}), mode, maxIterations: normalizeAgentMaxIterationsParameter(state.parameters.agentMaxIterations) },
        identity: { ...(existing?.identity?.additionalSettings ? { additionalSettings: existing.identity.additionalSettings } : {}), userDisplayName: readTrimmedInputValue(requireInput(modal, 'user-name')) || null, assistantDisplayName: readTrimmedInputValue(requireInput(modal, 'assistant-name')) || null },
        prompts: { ...(existing?.prompts?.additionalSettings ? { additionalSettings: existing.prompts.additionalSettings } : {}), userSystemPrompt: state.prompts.userSystemPrompt, soaiSystemPromptEnabled: state.prompts.soaiSystemPromptEnabled },
        mcp: mcp.readConfig()
    };
    const workspacePath = workspace.getValue();
    if (workspacePath !== null) settings.workspacePath = workspacePath;
    return settings;
};

const readCredentialDrafts = (modal: Element): MessagingCredentialDrafts => ({
    telegram: {
        botToken: readCredential(modal, 'telegram', 'botToken'),
        webhookSecret: readCredential(modal, 'telegram', 'webhookSecret')
    },
    whatsapp: {
        accessToken: readCredential(modal, 'whatsapp', 'accessToken'),
        phoneNumberId: readCredential(modal, 'whatsapp', 'phoneNumberId'),
        businessAccountId: readCredential(modal, 'whatsapp', 'businessAccountId'),
        applicationId: readCredential(modal, 'whatsapp', 'applicationId'),
        apiVersion: readCredential(modal, 'whatsapp', 'apiVersion'),
        appSecret: readCredential(modal, 'whatsapp', 'appSecret'),
        verifyToken: readCredential(modal, 'whatsapp', 'verifyToken')
    },
    discord: {
        botToken: readCredential(modal, 'discord', 'botToken'),
        applicationId: readCredential(modal, 'discord', 'applicationId')
    }
});

const emptyMcp = {
    defaultTools: [],
    planTools: [],
    executeTools: [],
    serverConfigs: {},
    toolsEnabled: true,
    toolApprovalRequired: true
};

const readMessagingDraft = (modal: HTMLElement, options: MessagingAccountModalOptions, state: MessagingEditorState, mcp: McpFormController | null, workspace: WorkspacePathDraft | null): MessagingDraft => {
    const selectedAgentMode = readTrimmedSelectValue(requireSelect(modal, 'agent-mode'));
    const modelSettings =
        mcp && workspace
            ? buildSettings(modal, state, mcp, workspace, options.account?.modelSettings ?? null)
            : {
                  model: readTrimmedSelectValue(requireSelect(modal, 'model')) || null,
                  parameters: { ...buildStoredChatParameters(state.parameters) },
                  agent: { mode: isAgentMode(selectedAgentMode) ? selectedAgentMode : 'chat' },
                  mcp: options.account?.modelSettings.mcp ?? emptyMcp
              };
    return {
        mode: options.mode,
        platform: platformFromSelect(modal),
        label: readTrimmedInputValue(requireInput(modal, 'label')),
        credentials: readCredentialDrafts(modal),
        modelSettings,
        locale: readTrimmedSelectValue(requireSelect(modal, 'locale')) === 'it' ? 'it' : 'en',
        plaintextSecretRepliesEnabled: requireInput(modal, 'plaintext-secrets').checked,
        acceptMessagesFromAnyone: requireInput(modal, 'accept-anyone').checked,
        replaceExistingCallback: requireInput(modal, 'replace-callback').checked,
        authorizedSenders: requireInput(modal, 'accept-anyone').checked ? [] : readAuthorizedSenders(requireTextarea(modal, 'authorized-senders').value),
        mcpPresentation: { searchText: '', selectedMode: 'default', expandedGroups: [] }
    };
};

export { applyMessagingModelChange, applyMessagingParameterEditorState, initializeMessagingEditor, readMessagingDraft, syncCredentialSections, syncSenderAccessState };
export type { MessagingEditorState };

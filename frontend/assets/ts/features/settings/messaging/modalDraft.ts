/* SoAI - Messaging account canonical draft and admission [frontend/assets/ts/features/settings/messaging/modalDraft.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccountLocale, MessagingAuthorizedSender, MessagingPlatform } from '@core/api/contracts/messagingAccountContracts.ts';
import { doesAgentModeRequireMcpTools, resolveMcpToolFieldForAgentMode } from '@core/chat/agentModeMcpMapping.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';
import { getParameterMeta } from '@core/chat/parameters/chatParameterMeta.ts';
import { isReasoningEffortSupported } from '@core/chat/parameters/reasoningEffort.ts';
import type { McpToolMode } from '@core/mcp/configTypes.ts';
import { normalizeMcpConfigValues } from '@core/mcp/toolChangeSurfaces.ts';
import { getMessagingProviderDescriptor } from '@features/settings/messaging/descriptors.ts';
import { resolveMessagingModelOption } from '@features/settings/messaging/modelOptions.ts';
import type { MessagingModelOption } from '@features/settings/messaging/types.ts';

type MessagingCredentialDrafts = {
    telegram: { botToken: string; webhookSecret: string };
    whatsapp: { accessToken: string; phoneNumberId: string; businessAccountId: string; applicationId: string; apiVersion: string; appSecret: string; verifyToken: string };
    discord: { botToken: string; applicationId: string };
};

type MessagingMcpPresentation = {
    searchText: string;
    selectedMode: McpToolMode;
    expandedGroups: string[];
};

interface MessagingDraft {
    mode: 'create' | 'edit';
    platform: MessagingPlatform;
    label: string;
    credentials: MessagingCredentialDrafts;
    modelSettings: ConversationModelSettings;
    locale: MessagingAccountLocale;
    plaintextSecretRepliesEnabled: boolean;
    acceptMessagesFromAnyone: boolean;
    replaceExistingCallback: boolean;
    authorizedSenders: MessagingAuthorizedSender[];
    mcpPresentation: MessagingMcpPresentation;
}

interface MessagingDraftAdmissionOptions {
    requiredPlanTools: readonly string[];
    requiredExecuteTools: readonly string[];
    models: readonly MessagingModelOption[];
}

interface MessagingDraftAdmission {
    complete: boolean;
    valid: boolean;
    invalidFields: string[];
}

const sortStrings = (values: readonly string[]): string[] => [...values].sort((left, right) => left.localeCompare(right, 'en'));

const selectedCredentials = (draft: MessagingDraft): Record<string, string> => {
    const credentials = draft.credentials[draft.platform];
    return Object.fromEntries(Object.entries(credentials).sort(([left], [right]) => left.localeCompare(right, 'en')));
};

const hasMessagingCredentialReplacement = (draft: MessagingDraft): boolean => {
    const descriptor = getMessagingProviderDescriptor(draft.platform);
    const credentials = selectedCredentials(draft);
    return descriptor.fields.some((field) => {
        const value = credentials[field.key]?.trim() ?? '';
        return value !== '' && value !== field.defaultValue;
    });
};

const createMessagingDraftProjection = (draft: MessagingDraft): string => {
    const mcp = draft.modelSettings.mcp;
    const normalizedMcp = mcp ? normalizeMcpConfigValues({ ...mcp, knowledgeState: null }) : null;
    const modelSettings = {
        ...draft.modelSettings,
        ...(normalizedMcp
            ? {
                  mcp: {
                      ...mcp,
                      defaultTools: sortStrings(normalizedMcp.defaultTools),
                      planTools: sortStrings(normalizedMcp.planTools),
                      executeTools: sortStrings(normalizedMcp.executeTools),
                      serverConfigs: Object.fromEntries(Object.entries(normalizedMcp.serverConfigs).sort(([left], [right]) => left.localeCompare(right, 'en')))
                  }
              }
            : {})
    };
    return JSON.stringify({
        mode: draft.mode,
        platform: draft.platform,
        label: draft.label,
        credentials: selectedCredentials(draft),
        modelSettings,
        locale: draft.locale,
        plaintextSecretRepliesEnabled: draft.plaintextSecretRepliesEnabled,
        acceptMessagesFromAnyone: draft.acceptMessagesFromAnyone,
        replaceExistingCallback: draft.replaceExistingCallback,
        authorizedSenders: draft.authorizedSenders
    });
};

const validateCredentials = (draft: MessagingDraft): boolean => {
    const descriptor = getMessagingProviderDescriptor(draft.platform);
    const credentials = selectedCredentials(draft);
    const values = descriptor.fields.map((field) => credentials[field.key]?.trim() ?? '');
    if (draft.mode === 'edit' && !hasMessagingCredentialReplacement(draft)) return true;
    return descriptor.fields.every((field, index) => {
        const value = values[index] ?? '';
        return value.length >= field.minLength && value.length <= field.maxLength && (field.pattern === null || field.pattern.test(value));
    });
};

const validateParameters = (settings: ConversationModelSettings, models: readonly MessagingModelOption[]): boolean => {
    const parameters = settings.parameters;
    if (!parameters) return true;
    for (const [key, value] of Object.entries(parameters)) {
        if (key === 'additionalParameters' || value === null || value === undefined) continue;
        const metadata = getParameterMeta(key);
        if (!metadata || metadata.type !== 'number') continue;
        if (typeof value !== 'number' || !Number.isFinite(value)) return false;
        if (metadata.precision === 0 && !Number.isInteger(value)) return false;
        if (metadata.min !== undefined && value < metadata.min) return false;
        if (metadata.max !== undefined && value > metadata.max) return false;
    }
    const maxIterations = settings.agent?.maxIterations;
    const maxIterationsMetadata = getParameterMeta('agentMaxIterations');
    if (maxIterations !== undefined && (!Number.isInteger(maxIterations) || maxIterations < (maxIterationsMetadata?.min ?? 1) || maxIterations > (maxIterationsMetadata?.max ?? Number.MAX_SAFE_INTEGER))) return false;
    const selectedModel = resolveMessagingModelOption(models, settings.model);
    if (selectedModel && !isReasoningEffortSupported(parameters.reasoningEffort, selectedModel.supportedReasoningLevels)) return false;
    return true;
};

const validateSenders = (senders: readonly MessagingAuthorizedSender[]): boolean => {
    const senderIds = new Set<string>();
    for (const sender of senders) {
        const senderId = sender.senderId.trim();
        if (!senderId || senderId.length > 255 || senderIds.has(senderId)) return false;
        if (sender.displayLabel !== null && (!sender.displayLabel.trim() || sender.displayLabel.trim().length > 255)) return false;
        senderIds.add(senderId);
    }
    return true;
};

const validateMcp = (draft: MessagingDraft, options: MessagingDraftAdmissionOptions): boolean => {
    const mode = draft.modelSettings.agent?.mode ?? 'chat';
    const mcp = draft.modelSettings.mcp;
    if (!mcp) return !doesAgentModeRequireMcpTools(mode);
    if (!mcp.toolsEnabled) return !doesAgentModeRequireMcpTools(mode);
    if (!doesAgentModeRequireMcpTools(mode)) return true;
    const selected = mcp[resolveMcpToolFieldForAgentMode(mode)];
    const required = mode === 'plan' ? options.requiredPlanTools : options.requiredExecuteTools;
    return required.every((toolName) => selected.includes(toolName));
};

const validateMessagingDraft = (draft: MessagingDraft, options: MessagingDraftAdmissionOptions): MessagingDraftAdmission => {
    const invalidFields: string[] = [];
    const labelComplete = draft.label.trim().length > 0 && draft.label.trim().length <= 120;
    const modelComplete = Boolean(draft.modelSettings.model?.trim());
    if (!labelComplete) invalidFields.push('label');
    if (!modelComplete) invalidFields.push('model');
    if (!validateCredentials(draft)) invalidFields.push('credentials');
    if (!validateParameters(draft.modelSettings, options.models)) invalidFields.push('parameters');
    const senderAccessValid = draft.acceptMessagesFromAnyone ? draft.authorizedSenders.length === 0 : validateSenders(draft.authorizedSenders);
    if (!senderAccessValid) invalidFields.push('authorizedSenders');
    if (!validateMcp(draft, options)) invalidFields.push('mcp');
    return {
        complete: labelComplete && modelComplete && !invalidFields.includes('credentials'),
        valid: invalidFields.length === 0,
        invalidFields
    };
};

const applyMessagingModelSelection = (draft: MessagingDraft, models: readonly MessagingModelOption[], modelId: string, source: 'initialize' | 'user'): void => {
    const entry = resolveMessagingModelOption(models, modelId);
    const parameters = draft.modelSettings.parameters ?? {};
    draft.modelSettings.model = modelId;
    draft.modelSettings.parameters = parameters;
    if (source === 'initialize' && parameters.contextWindowTokens !== null && parameters.contextWindowTokens !== undefined) return;
    parameters.contextWindowTokens = entry?.contextWindowTokens ?? null;
    if (source === 'user' && typeof entry?.contextWindowTokens === 'number') {
        const completionTokens = parameters.maxCompletionTokens;
        if (typeof completionTokens === 'number' && completionTokens > entry.contextWindowTokens) parameters.maxCompletionTokens = entry.contextWindowTokens;
    }
};

export { applyMessagingModelSelection, createMessagingDraftProjection, hasMessagingCredentialReplacement, validateMessagingDraft };
export type { MessagingCredentialDrafts, MessagingDraft, MessagingDraftAdmission, MessagingDraftAdmissionOptions, MessagingMcpPresentation };

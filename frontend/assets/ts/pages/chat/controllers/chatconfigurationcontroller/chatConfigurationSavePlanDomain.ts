/* SoAI - Ordered chat configuration save plan [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSavePlanDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import type { SaveUnit } from '@core/save/public.ts';
import type { ChatParameters, ConversationSettingsActionResult, ConversationSettingsSavePlanInput } from '@features/chat/public.ts';
import type { ConfigurationControllerHost, ConfigurationControllerStateAccess, ConversationSettingsSavePlan } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';
import type { ConfigurationModelSelectionStateManager } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelSelectionStateManager.ts';
import { areParameterValuesEqual, normalizeConversationSettingsAction } from '@pages/chat/controllers/chatconfigurationcontroller/configurationChangeTracking.ts';
import { PARAMETER_SECTION_KEYS } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetParameterSectionsDomain.ts';
import type { ChatConfigurationSaveUnitId } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSaveOutcomeDomain.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ChatConfigurationSavePlanAccess {
    host: ConfigurationControllerHost;
    hasWritableConversation(): boolean;
    parameters(): ChatParameters | null;
    model(): string | null;
    comparisonModels(): string[];
    parametersDirty(): boolean;
    conversationParametersDirty(): boolean;
    modelDirty(): boolean;
    preferencesDirty(): boolean;
    coreValid(): boolean;
    settingsPlan(): ConversationSettingsSavePlan;
    projectionEffectsDirty(): boolean;
    editSession(): ChatParameters | null;
    isEditSessionActive(session: ChatParameters | null): boolean;
    commitConversationCore(parameters: ChatParameters, models: { primary: string | null; comparison: string[] }, parametersDirty: boolean, modelDirty: boolean): void;
    commitAllCore(): Promise<boolean>;
    retryProjectionEffects(): Promise<boolean>;
    stop(error: Error, unitId: ChatConfigurationSaveUnitId): Readonly<{ type: 'stop' }>;
    invalidate(unitId: ChatConfigurationSaveUnitId): boolean;
    complete(unitId: ChatConfigurationSaveUnitId): void;
}

const captureParameters = (access: ChatConfigurationSavePlanAccess): ChatParameters => {
    const parameters = access.parameters();
    if (!parameters) throw new Error('Chat configuration save requires staged parameters.');
    return cloneChatParameters(parameters);
};

const rejectUnpreparedSave = (): never => {
    throw new Error('Chat configuration save units must be prepared before execution.');
};

const runPreparedUnit = async (access: ChatConfigurationSavePlanAccess, unitId: ChatConfigurationSaveUnitId, operation: () => Promise<ConversationSettingsActionResult>): Promise<ConversationSettingsActionResult | Readonly<{ type: 'stop' }>> => {
    try {
        const result = await operation();
        access.complete(unitId);
        return result;
    } catch (error) {
        return access.stop(ensureError(error), unitId);
    }
};

const haveConversationParameterChanges = (current: ChatParameters | null, baseline: ChatParameters | null): boolean => {
    if (!current || !baseline) return false;
    return PARAMETER_SECTION_KEYS.completion.some((key) => !areParameterValuesEqual(key, current[key], baseline[key]));
};

const applyConversationParameterProjection = (pageParameters: ChatParameters, baseline: ChatParameters, captured: ChatParameters): ChatParameters => {
    const next = cloneChatParameters(pageParameters);
    for (const key of PARAMETER_SECTION_KEYS.completion) {
        next[key] = captured[key];
        baseline[key] = captured[key];
    }
    return next;
};

const commitConversationCoreProjection = (options: { active: boolean; captured: ChatParameters; baseline: ChatParameters | null; parametersDirty: boolean; models: { primary: string | null; comparison: string[] }; modelDirty: boolean; state: ConfigurationControllerStateAccess; modelController: ConfigurationModelSelectionStateManager; refresh(): void }): void => {
    if (!options.active) return;
    if (options.parametersDirty && options.baseline) options.state.setParameters(applyConversationParameterProjection(options.state.getParameters(), options.baseline, options.captured));
    if (options.modelDirty) {
        options.state.setCurrentModel(options.models.primary);
        options.modelController.rebase(options.models);
    }
    options.refresh();
};

const normalizeConversationSettingsSavePlan = (plan: ConversationSettingsSavePlanInput | null): ConversationSettingsSavePlan => ({
    conversation: normalizeConversationSettingsAction(plan?.conversation ?? null),
    knowledge: normalizeConversationSettingsAction(plan?.knowledge ?? null),
    tools: normalizeConversationSettingsAction(plan?.tools ?? null)
});

const createChatConfigurationSaveUnits = (access: ChatConfigurationSavePlanAccess): readonly SaveUnit[] => [
    {
        id: 'conversation',
        hasChanges: () => {
            const action = access.settingsPlan().conversation;
            return Boolean(action?.hasChanges) || (access.hasWritableConversation() && (access.conversationParametersDirty() || access.modelDirty()));
        },
        isValid: () => access.coreValid() && (access.settingsPlan().conversation?.isValid ?? true),
        save: rejectUnpreparedSave,
        prepare: () => {
            const session = access.editSession();
            const parameters = captureParameters(access);
            const model = access.model();
            const comparisonModels = access.comparisonModels();
            const parametersDirty = access.conversationParametersDirty();
            const modelDirty = access.modelDirty();
            const action = access.settingsPlan().conversation;
            const writable = access.hasWritableConversation();
            const persist = writable && (parametersDirty || modelDirty || action?.hasChanges) ? access.host.prepareStagedConversationConfiguration({ parameters, model, comparisonModels, parametersDirty, modelDirty }) : null;
            return {
                save: () =>
                    runPreparedUnit(access, 'conversation', async () => {
                        const persistence = persist ? await persist() : { active: true, degraded: false };
                        const actionResult = action?.hasChanges && action.handler ? await action.handler() : undefined;
                        if (persistence.active && writable && access.isEditSessionActive(session) && (parametersDirty || modelDirty)) access.commitConversationCore(parameters, { primary: model, comparison: comparisonModels }, parametersDirty, modelDirty);
                        return persistence.degraded ? { type: 'continue-degraded' } : actionResult;
                    })
            };
        }
    },
    {
        id: 'knowledge',
        hasChanges: () => Boolean(access.settingsPlan().knowledge?.hasChanges),
        isValid: () => access.settingsPlan().knowledge?.isValid ?? true,
        save: rejectUnpreparedSave,
        prepare: () => {
            const action = access.settingsPlan().knowledge;
            return {
                isValid: () => (action?.isStillValid() ?? true) || access.invalidate('knowledge'),
                save: () =>
                    runPreparedUnit(access, 'knowledge', async () => {
                        return await action?.handler?.();
                    })
            };
        }
    },
    {
        id: 'tools',
        hasChanges: () => Boolean(access.settingsPlan().tools?.hasChanges),
        isValid: () => access.settingsPlan().tools?.isValid ?? true,
        save: rejectUnpreparedSave,
        prepare: () => {
            const action = access.settingsPlan().tools;
            return {
                isValid: () => (action?.isStillValid() ?? true) || access.invalidate('tools'),
                save: () =>
                    runPreparedUnit(access, 'tools', async () => {
                        return await action?.handler?.();
                    })
            };
        }
    },
    {
        id: 'preferences',
        hasChanges: () => access.preferencesDirty() || access.projectionEffectsDirty() || (!access.hasWritableConversation() && (access.parametersDirty() || access.modelDirty())) || Boolean(access.settingsPlan().conversation?.hasChanges),
        isValid: () => access.coreValid(),
        save: rejectUnpreparedSave,
        prepare: () => {
            const session = access.editSession();
            const parameters = captureParameters(access);
            const model = access.model();
            const coreChanges = access.parametersDirty() || access.modelDirty();
            const retryProjection = access.projectionEffectsDirty();
            const persist = access.host.prepareStagedConfigurationPreferences(parameters, model, () => access.isEditSessionActive(session));
            return {
                save: () =>
                    runPreparedUnit(access, 'preferences', async () => {
                        await persist();
                        const active = access.isEditSessionActive(session);
                        const degraded = coreChanges && active ? await access.commitAllCore() : retryProjection && active ? await access.retryProjectionEffects() : false;
                        return degraded ? { type: 'continue-degraded' } : undefined;
                    })
            };
        }
    }
];

export { commitConversationCoreProjection, createChatConfigurationSaveUnits, haveConversationParameterChanges, normalizeConversationSettingsSavePlan };
export type { ChatConfigurationSavePlanAccess };

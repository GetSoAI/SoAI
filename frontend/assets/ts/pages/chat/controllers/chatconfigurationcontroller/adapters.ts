/* SoAI - Chat preset section staging adapters [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_WIRE_TO_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { serializeChatPresetSections } from '@core/api/contracts/webuiChatPresetSectionContracts.ts';
import type { ChatPresetSections, WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { CHAT_PRESET_SECTION_DEFINITIONS, deriveHypotheticalKnowledgeMcpConfig, hasMcpConfigChanges, isAgentModeRequiringTools, isChatConversationSettingsWritable, mergeMcpPreset, snapshotMcpPreset, type ChatConversationSettingsManager, type ChatParameters, type ChatPresetSectionId, type ConversationSettingsControllerBundle, type IdentityPromptsSnapshot, type McpFormValues, type RagConfig } from '@features/chat/public.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts';
import { mergeParameterPresetSection, PARAMETER_SECTION_KEYS, snapshotParameterSection, snapshotParameterSections, type ParameterPresetSectionId } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetParameterSectionsDomain.ts';
import type { ConfigurationModelSnapshot } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelSelectionStateManager.ts';
import type { ChatPresetApplyResult, ChatPresetConfigurationPort, ChatPresetSectionChoice, ChatPresetSnapshotResult } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';

type PresetWorkingState = {
    parameters: ChatParameters;
    model: ConfigurationModelSnapshot;
    identity: IdentityPromptsSnapshot | null;
    rag: RagConfig | null;
    mcp: McpFormValues | null;
    workspacePath: string | null;
};

type PresetPreflight = Readonly<{
    state: PresetWorkingState;
    appliedSections: readonly ChatPresetSectionId[];
    skippedValues: readonly string[];
}>;

const PARAMETER_SECTION_IDS: readonly ParameterPresetSectionId[] = ['general', 'appearance', 'completion', 'voice'];
const IDENTITY_SECTION_FIELDS: Readonly<Record<'general' | 'completion', ReadonlySet<string>>> = Object.freeze({
    general: new Set(['user_display_name', 'assistant_display_name']),
    completion: new Set(['user_system_prompt', 'user_system_prompt_lock_enabled', 'soai_system_prompt_enabled'])
});

const recordsEqual = <First, Second>(first: First, second: Second): boolean => JSON.stringify(first) === JSON.stringify(second);

const snapshotRag = (config: RagConfig): JsonObject => ({ enabled: config.enabled, 'retrieval_strategy': config.retrievalStrategy, 'top_k': config.topK, 'similarity_threshold': config.similarityThreshold, 'chunking_strategy': config.chunkingStrategy, 'chunk_size': config.chunkSize, 'chunk_overlap': config.chunkOverlap, 'embedding_model': config.embeddingModel });

const addIdentitySections = (sections: ChatPresetSections, snapshot: IdentityPromptsSnapshot): void => {
    const general = sections.general ?? {};
    general['user_display_name'] = snapshot.userDisplayName;
    general['assistant_display_name'] = snapshot.assistantDisplayName;
    sections.general = general;
    const completion = sections.completion ?? {};
    completion['user_system_prompt'] = snapshot.userSystemPrompt;
    completion['user_system_prompt_lock_enabled'] = snapshot.userSystemPromptLockEnabled;
    completion['soai_system_prompt_enabled'] = snapshot.soaiSystemPromptEnabled;
    sections.completion = completion;
};

class ChatPresetSectionAdapterRegistry implements ChatPresetConfigurationPort {
    readonly #configuration: ChatConfigurationController;
    readonly #settings: ChatConversationSettingsManager;

    constructor(configuration: ChatConfigurationController, settings: ChatConversationSettingsManager) {
        this.#configuration = configuration;
        this.#settings = settings;
    }

    sectionChoices(): readonly ChatPresetSectionChoice[] {
        const controllers = this.#controllers();
        const coreHydrated = this.#configuration.isEditingConfiguration();
        const parameterEligible = (sectionId: ParameterPresetSectionId): boolean => PARAMETER_SECTION_KEYS[sectionId].some((key) => !this.#configuration.isParameterLocked(key));
        const identityHydrated = this.#hasWritableConversation() && controllers.identityPromptsController.isHydrated();
        const authorityLocked = this.#isAuthorityLocked();
        const modelSnapshot = this.#configuration.model.snapshot();
        const hydrated: Readonly<Record<ChatPresetSectionId, boolean>> = {
            general: coreHydrated && (parameterEligible('general') || identityHydrated || (modelSnapshot.model !== null && this.#configuration.canStagePresetModel(modelSnapshot))),
            appearance: coreHydrated && parameterEligible('appearance'),
            completion: coreHydrated && !authorityLocked && (parameterEligible('completion') || identityHydrated),
            voice: coreHydrated && !authorityLocked && parameterEligible('voice'),
            files: controllers.workspacePathController.isHydrated(),
            knowledge: controllers.ragController.isHydrated(),
            tools: controllers.mcpController.isHydrated() && controllers.mcpController.isEditable()
        };
        return CHAT_PRESET_SECTION_DEFINITIONS.map((definition) => ({ id: definition.id, eligible: hydrated[definition.id], hydrated: hydrated[definition.id], reason: hydrated[definition.id] ? null : i18n.t('chat.configuration.presetLibrary.editor.sectionUnavailable') }));
    }

    snapshot(selectedSections: ReadonlySet<ChatPresetSectionId>): ChatPresetSnapshotResult {
        try {
            const controllers = this.#controllers();
            const choiceMap = new Map(this.sectionChoices().map((choice) => [choice.id, choice]));
            for (const sectionId of selectedSections) {
                const choice = choiceMap.get(sectionId);
                if (!choice?.eligible || !choice.hydrated) return { status: 'invalid', message: choice?.reason ?? 'A selected section is unavailable.' };
            }
            const prunedValues: string[] = [];
            const sections = snapshotParameterSections(this.#configuration.getWorkingParameters(), selectedSections, (key) => !this.#configuration.isParameterLocked(key));
            const modelSnapshot = this.#configuration.model.snapshot();
            if (selectedSections.has('general') && modelSnapshot.model) {
                if (this.#configuration.canStagePresetModel(modelSnapshot)) (sections.general ??= {})['model'] = modelSnapshot.model;
                else prunedValues.push('general:model');
            }
            const identity = controllers.identityPromptsController.workingSnapshot();
            if (this.#hasWritableConversation() && (selectedSections.has('general') || selectedSections.has('completion')) && identity) addIdentitySections(sections, identity);
            if (!selectedSections.has('general')) delete sections.general;
            if (!selectedSections.has('completion')) delete sections.completion;
            if (selectedSections.has('files')) sections.files = { 'workspace_path': controllers.workspacePathController.workingOverride() };
            const rag = controllers.ragController.workingConfig();
            if (selectedSections.has('knowledge') && rag) {
                sections.knowledge = snapshotRag(rag);
                if (typeof rag.embeddingModel === 'string' && !controllers.ragController.isEmbeddingModelAvailable(rag.embeddingModel)) {
                    delete sections.knowledge['embedding_model'];
                    prunedValues.push('knowledge:embedding_model');
                }
            }
            const mcp = controllers.mcpController.workingValues();
            if (selectedSections.has('tools') && mcp) sections.tools = snapshotMcpPreset(mcp, controllers.mcpController.tools(), controllers.mcpController.baselineConfig(), this.#isToolsEnabledLocked());
            const voice = sections.voice;
            if (voice) {
                const availability = modelSnapshot.voiceModelAvailability;
                const tts = voice['voice_tts_model'];
                const stt = voice['voice_stt_model'];
                if (typeof tts === 'string' && tts !== 'auto' && !availability.tts.has(tts)) {
                    delete voice['voice_tts_model'];
                    prunedValues.push('voice:voice_tts_model');
                }
                if (typeof stt === 'string' && stt !== 'auto' && !availability.stt.has(stt)) {
                    delete voice['voice_stt_model'];
                    prunedValues.push('voice:voice_stt_model');
                }
                if (Object.keys(voice).length === 0) delete sections.voice;
            }
            const serialized = serializeChatPresetSections(sections);
            if (Object.keys(serialized).length === 0) return { status: 'invalid', message: i18n.t('chat.configuration.presetLibrary.editor.sectionUnavailable') };
            return { status: 'ready', sections: serialized, prunedValues };
        } catch (error) {
            errorHandler.warn('ChatPresetLibrary', 'Preset snapshot validation failed', ensureError(error));
            return { status: 'invalid', message: i18n.t('chat.configuration.presetLibrary.editor.sectionUnavailable') };
        }
    }

    async apply(record: WebuiChatPresetRecord, isSessionActive: () => boolean): Promise<ChatPresetApplyResult | null> {
        await this.#settings.awaitPresetHydration(record.sections);
        if (!isSessionActive()) return null;
        const controllers = this.#controllers();
        const preflight = this.#preflight(record.sections, controllers);
        if (!preflight) throw new Error('Preset values are not valid in the current configuration.');
        const next = preflight.state;
        const previous = this.#workingState(controllers);
        this.#configuration.commitPresetWorkingState(next.parameters, next.model);
        if (next.identity) controllers.identityPromptsController.commitWorkingSnapshot(next.identity);
        if (next.rag) controllers.ragController.commitWorkingConfig(next.rag);
        if (next.mcp) controllers.mcpController.commitWorkingValues(next.mcp);
        controllers.workspacePathController.commitWorkingOverride(next.workspacePath);
        this.#configuration.refreshPresetWorkingPresentation();
        controllers.identityPromptsController.refreshWorkingPresentation();
        controllers.ragController.refreshWorkingPresentation();
        controllers.mcpController.refreshWorkingPresentation();
        controllers.workspacePathController.refreshWorkingPresentation();
        const changed = !recordsEqual(previous, next);
        return { changed, appliedSections: preflight.appliedSections, skippedValues: preflight.skippedValues };
    }

    dirtySections(record: WebuiChatPresetRecord): readonly ChatPresetSectionId[] {
        const controllers = this.#controllers();
        const baseline = this.#configuration.getParameterBaseline();
        const working = this.#configuration.getWorkingParameters();
        const dirty = new Set<ChatPresetSectionId>();
        if (baseline) for (const sectionId of PARAMETER_SECTION_IDS) if (record.sections[sectionId] && !recordsEqual(snapshotParameterSection(working, sectionId), snapshotParameterSection(baseline, sectionId))) dirty.add(sectionId);
        if (record.sections.general && this.#configuration.model.workingModel() !== this.#configuration.model.baselineModel()) dirty.add('general');
        const identity = controllers.identityPromptsController;
        if (!recordsEqual(identity.workingSnapshot(), identity.baselineSnapshot())) {
            if (record.sections.general) dirty.add('general');
            if (record.sections.completion) dirty.add('completion');
        }
        if (record.sections.knowledge && !recordsEqual(controllers.ragController.workingConfig(), controllers.ragController.baselineConfig())) dirty.add('knowledge');
        const mcpValues = controllers.mcpController.workingValues();
        const mcpBaseline = controllers.mcpController.baselineConfig();
        if (record.sections.tools && mcpValues && mcpBaseline && hasMcpConfigChanges(mcpValues, mcpBaseline)) dirty.add('tools');
        if (record.sections.files && controllers.workspacePathController.isDirty()) dirty.add('files');
        return [...dirty];
    }

    #preflight(sections: ChatPresetSections, controllers: ConversationSettingsControllerBundle): PresetPreflight | null {
        const applicableSections = new Set<ChatPresetSectionId>();
        const appliedSections = new Set<ChatPresetSectionId>();
        const skippedValues: string[] = [];
        const identityEligible = this.#hasWritableConversation();
        const identityHydrated = identityEligible && controllers.identityPromptsController.isHydrated();
        const authorityLocked = this.#isAuthorityLocked();
        for (const definition of CHAT_PRESET_SECTION_DEFINITIONS) {
            const section = sections[definition.id];
            if (section && this.#isApplySectionHydrated(definition.id, section, controllers, identityEligible, identityHydrated, authorityLocked)) applicableSections.add(definition.id);
        }
        for (const definition of CHAT_PRESET_SECTION_DEFINITIONS) if (sections[definition.id] && !applicableSections.has(definition.id)) skippedValues.push(`section:${definition.id}`);
        const modelValue = applicableSections.has('general') ? sections.general?.['model'] : undefined;
        let model = this.#configuration.model.snapshot();
        let modelChanged = false;
        if (typeof modelValue === 'string') {
            const candidate = this.#configuration.model.snapshot(modelValue);
            if (this.#configuration.canStagePresetModel(candidate)) {
                model = candidate;
                modelChanged = candidate.model !== this.#configuration.model.workingModel();
                appliedSections.add('general');
            } else {
                skippedValues.push(`general:model:${modelValue}`);
            }
        }
        let parameters = cloneChatParameters(this.#configuration.getWorkingParameters());
        for (const sectionId of PARAMETER_SECTION_IDS) {
            let section = sections[sectionId];
            if (section) {
                const filtered: JsonObject = {};
                const parameterKeys = new Set<string>(PARAMETER_SECTION_KEYS[sectionId]);
                for (const [wireKey, value] of Object.entries(section)) {
                    const parameterKey = CHAT_WIRE_TO_PARAMETER_KEYS[wireKey] ?? wireKey;
                    if (!parameterKeys.has(parameterKey)) continue;
                    if (this.#configuration.isParameterLocked(parameterKey)) skippedValues.push(`${sectionId}:${wireKey}:locked`);
                    else filtered[wireKey] = value;
                }
                section = filtered;
            }
            if (sectionId === 'voice' && section) {
                const availability = model.voiceModelAvailability;
                section = { ...section };
                const tts = section['voice_tts_model'];
                const stt = section['voice_stt_model'];
                if (typeof tts === 'string' && tts !== 'auto' && !availability.tts.has(tts)) {
                    delete section['voice_tts_model'];
                    skippedValues.push(`voice:voice_tts_model:${tts}`);
                }
                if (typeof stt === 'string' && stt !== 'auto' && !availability.stt.has(stt)) {
                    delete section['voice_stt_model'];
                    skippedValues.push(`voice:voice_stt_model:${stt}`);
                }
            }
            if (section && Object.keys(section).length > 0 && applicableSections.has(sectionId)) {
                parameters = mergeParameterPresetSection(parameters, sectionId, section);
                appliedSections.add(sectionId);
            }
        }
        if ((modelChanged || appliedSections.has('completion')) && !this.#configuration.canCommitPresetWorkingState(model, parameters)) return null;
        const generalIdentity = this.#identitySection(sections.general, 'general', applicableSections.has('general'), identityHydrated, skippedValues);
        const completionIdentity = this.#identitySection(sections.completion, 'completion', applicableSections.has('completion'), identityHydrated, skippedValues);
        const identityFieldsPresent = Boolean(generalIdentity || completionIdentity);
        const identity = identityFieldsPresent ? controllers.identityPromptsController.mergePresetSections(generalIdentity ?? undefined, completionIdentity ?? undefined) : controllers.identityPromptsController.workingSnapshot();
        if (identityFieldsPresent && !identity) return null;
        if (generalIdentity) appliedSections.add('general');
        if (completionIdentity) appliedSections.add('completion');
        let knowledgeSection = sections.knowledge;
        if (applicableSections.has('knowledge') && knowledgeSection) {
            const embeddingModel = knowledgeSection['embedding_model'];
            if (typeof embeddingModel === 'string' && !controllers.ragController.isEmbeddingModelAvailable(embeddingModel)) {
                knowledgeSection = { ...knowledgeSection };
                delete knowledgeSection['embedding_model'];
                skippedValues.push(`knowledge:embedding_model:${embeddingModel}`);
            }
        }
        const knowledgeApplied = Boolean(applicableSections.has('knowledge') && knowledgeSection && Object.keys(knowledgeSection).length > 0);
        const rag = knowledgeApplied && knowledgeSection ? controllers.ragController.mergePreset(knowledgeSection) : controllers.ragController.workingConfig();
        if (knowledgeApplied && !rag) return null;
        if (knowledgeApplied) appliedSections.add('knowledge');
        const currentMcp = controllers.mcpController.workingValues();
        const mcpBaseline = controllers.mcpController.baselineConfig();
        const hypotheticalMcpBaseline = mcpBaseline && rag ? deriveHypotheticalKnowledgeMcpConfig(mcpBaseline, rag.enabled, model.supportsToolCalling) : mcpBaseline;
        const mcpMerge = applicableSections.has('tools') && sections.tools && currentMcp && hypotheticalMcpBaseline ? mergeMcpPreset(currentMcp, sections.tools, controllers.mcpController.tools(), hypotheticalMcpBaseline, this.#isToolsEnabledLocked()) : null;
        if (applicableSections.has('tools') && !mcpMerge) return null;
        if (mcpMerge) {
            skippedValues.push(...mcpMerge.skippedValues);
            appliedSections.add('tools');
        }
        const workspaceValue = applicableSections.has('files') ? sections.files?.['workspace_path'] : undefined;
        const workspacePath = workspaceValue === undefined ? controllers.workspacePathController.workingOverride() : workspaceValue;
        if (workspacePath !== null && typeof workspacePath !== 'string') return null;
        if (applicableSections.has('files') && !controllers.workspacePathController.canCommitWorkingOverride(workspacePath)) return null;
        if (applicableSections.has('files')) appliedSections.add('files');
        return { state: { parameters, model, identity, rag, mcp: mcpMerge?.values ?? currentMcp, workspacePath }, appliedSections: [...appliedSections], skippedValues };
    }

    #isApplySectionHydrated(sectionId: ChatPresetSectionId, section: JsonObject, controllers: ConversationSettingsControllerBundle, identityEligible: boolean, identityHydrated: boolean, authorityLocked: boolean): boolean {
        if (sectionId === 'files') return controllers.workspacePathController.isHydrated();
        if (sectionId === 'knowledge') return controllers.ragController.isHydrated() && (typeof section['embedding_model'] !== 'string' || controllers.ragController.isEmbeddingModelCatalogHydrated());
        if (sectionId === 'tools') return controllers.mcpController.isHydrated() && controllers.mcpController.isEditable();
        if (!this.#configuration.isEditingConfiguration()) return false;
        if (authorityLocked && (sectionId === 'completion' || sectionId === 'voice')) return false;
        if (sectionId === 'voice') return this.#configuration.model.isCatalogHydrated();
        if (sectionId === 'general' && typeof section['model'] === 'string' && !this.#configuration.model.isCatalogHydrated()) return false;
        if (sectionId !== 'general' && sectionId !== 'completion') return true;
        return !identityEligible || !Object.keys(section).some((field) => IDENTITY_SECTION_FIELDS[sectionId].has(field)) || identityHydrated;
    }

    #identitySection(section: JsonObject | undefined, sectionId: 'general' | 'completion', applicable: boolean, identityHydrated: boolean, skippedValues: string[]): JsonObject | null {
        if (!section || !applicable) return null;
        const identityFields = Object.fromEntries(Object.entries(section).filter(([field]) => IDENTITY_SECTION_FIELDS[sectionId].has(field)));
        if (Object.keys(identityFields).length === 0) return null;
        if (identityHydrated) return identityFields;
        skippedValues.push(...Object.keys(identityFields).map((field) => `${sectionId}:${field}:unavailable`));
        return null;
    }

    #hasWritableConversation(): boolean {
        return isChatConversationSettingsWritable(this.#settings.host.data.getCurrentConversation());
    }

    #isAuthorityLocked(): boolean {
        return isConversationAuthorityLocked(this.#settings.host.data.getCurrentConversation());
    }

    #isToolsEnabledLocked(): boolean {
        const conversation = this.#settings.host.data.getCurrentConversation();
        return isAgentModeRequiringTools(conversation?.modelSettings) || Boolean(conversation?.id && this.#settings.host.data.isConversationExecuting(conversation.id));
    }

    #workingState(controllers: ConversationSettingsControllerBundle): PresetWorkingState {
        return { parameters: cloneChatParameters(this.#configuration.getWorkingParameters()), model: this.#configuration.model.snapshot(), identity: controllers.identityPromptsController.workingSnapshot(), rag: controllers.ragController.workingConfig(), mcp: controllers.mcpController.workingValues(), workspacePath: controllers.workspacePathController.workingOverride() };
    }

    #controllers(): ConversationSettingsControllerBundle {
        return this.#settings.presetControllers();
    }
}

export { ChatPresetSectionAdapterRegistry };

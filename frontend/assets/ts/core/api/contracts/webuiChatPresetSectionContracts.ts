/* SoAI - WebUI chat preset section wire validation [frontend/assets/ts/core/api/contracts/webuiChatPresetSectionContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPresetSectionId, ChatPresetSections } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { isChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { isReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { isChatServiceTier } from '@core/chat/parameters/serviceTier.ts';
import { isUnicodeScalarText, trimPythonWhitespace } from '@core/primitives/text.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { isJsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const SECTION_FIELDS: Record<ChatPresetSectionId, readonly string[]> = {
    general: ['model', 'user_display_name', 'assistant_display_name', 'hide_real_model', 'conversation_pdf_export_enabled', 'new_conversation_inherit_last_settings', 'ctrl_enter_send_enabled'],
    appearance: ['text_zoom', 'widescreen_mode', 'rich_text_enabled', 'inline_multimedia_previews_enabled', 'auto_title_generation', 'show_activities', 'show_activity_elapsed_time', 'hide_automation_runs', 'hide_messaging_conversations', 'notify_on_completion', 'notify_on_error', 'microphone_sound_effects_enabled', 'input_action_voice_enabled', 'input_action_call_enabled', 'input_action_file_upload_enabled', 'input_action_camera_enabled', 'input_action_prompts_enabled', 'input_action_token_counter_enabled', 'input_action_new_conversation_enabled', 'input_action_character_map_enabled', 'input_action_mobile_auxiliary_action'],
    completion: ['user_system_prompt', 'user_system_prompt_lock_enabled', 'soai_system_prompt_enabled', 'context_window_tokens', 'reasoning_effort', 'reasoning_effort_send_enabled', 'max_completion_tokens', 'max_completion_tokens_send_enabled', 'agent_max_iterations', 'temperature', 'top_p', 'top_p_send_enabled', 'frequency_penalty', 'frequency_penalty_send_enabled', 'presence_penalty', 'presence_penalty_send_enabled', 'stop', 'stop_send_enabled', 'top_logprobs', 'logprobs_send_enabled', 'service_tier'],
    voice: ['voice_tts_model', 'voice_stt_model'],
    files: ['workspace_path'],
    knowledge: ['enabled', 'retrieval_strategy', 'top_k', 'similarity_threshold', 'chunking_strategy', 'chunk_size', 'chunk_overlap', 'embedding_model'],
    tools: ['tools_enabled', 'tool_approval_required', 'servers', 'modes']
};

const SECTION_IDS: readonly ChatPresetSectionId[] = ['general', 'appearance', 'completion', 'voice', 'files', 'knowledge', 'tools'];
const RETRIEVAL_STRATEGIES = new Set(['similarity', 'mmr', 'hybrid']);
const CHUNKING_STRATEGIES = new Set(['token_based', 'fixed_size', 'paragraph', 'semantic']);
const TOOL_MODES = new Set(['default', 'plan', 'execute']);

const fail = (label: string): never => {
    throw new TypeError(`${label} is invalid.`);
};

type OptionalJsonValue = JsonValue | undefined;

const requireString = (value: OptionalJsonValue, label: string, nullable: boolean, maximumCodePoints?: number): void => {
    if (value === null && nullable) return;
    const stringValue = typeof value === 'string' ? value : fail(label);
    if (stringValue.length === 0 || trimPythonWhitespace(stringValue) !== stringValue || !isUnicodeScalarText(stringValue)) fail(label);
    if (maximumCodePoints !== undefined && Array.from(stringValue).length > maximumCodePoints) fail(label);
};

const requireBoolean = (value: OptionalJsonValue, label: string): void => {
    if (typeof value !== 'boolean') fail(label);
};

const requireNumber = (value: OptionalJsonValue, label: string, minimum: number, maximum: number): void => {
    if (typeof value !== 'number' || !Number.isFinite(value) || Object.is(value, -0) || value < minimum || value > maximum) fail(label);
};

const requireInteger = (value: OptionalJsonValue, label: string, minimum: number, maximum: number, nullable = false): void => {
    if (value === null && nullable) return;
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || Object.is(value, -0) || value < minimum || value > maximum) fail(label);
};

const requireEnum = (value: OptionalJsonValue, label: string, allowed: ReadonlySet<string>, nullable = false): void => {
    if (value === null && nullable) return;
    if (typeof value !== 'string' || !allowed.has(value)) fail(label);
};

const requireBooleanMap = (value: OptionalJsonValue, label: string): void => {
    const record = requireRecord(value, label);
    if (Object.keys(record).length === 0) fail(label);
    Object.entries(record).forEach(([key, entry]) => {
        requireString(key, `${label} key`, false);
        requireBoolean(entry, `${label}.${key}`);
    });
};

const requireToolModes = (value: OptionalJsonValue, label: string): void => {
    const modes = requireRecord(value, label);
    if (Object.keys(modes).length === 0) fail(label);
    Object.entries(modes).forEach(([mode, tools]) => {
        if (!TOOL_MODES.has(mode)) fail(label);
        requireBooleanMap(tools, `${label}.${mode}`);
    });
};

const validateGeneral = (field: string, value: JsonValue, label: string): void => {
    if (field === 'model') return requireString(value, label, false);
    if (field === 'user_display_name' || field === 'assistant_display_name') return requireString(value, label, true, 50);
    requireBoolean(value, label);
};

const validateAppearance = (field: string, value: JsonValue, label: string): void => {
    if (field === 'text_zoom') return requireNumber(value, label, 0.5, 1.5);
    if (field === 'input_action_mobile_auxiliary_action') {
        if (typeof value !== 'string' || !isChatMobileAuxiliaryAction(value)) fail(label);
        return;
    }
    requireBoolean(value, label);
};

const validateCompletion = (field: string, value: JsonValue, label: string): void => {
    if (field === 'user_system_prompt') return requireString(value, label, true);
    if (field.endsWith('_enabled')) return requireBoolean(value, label);
    if (field === 'context_window_tokens') return requireInteger(value, label, 1, Number.MAX_SAFE_INTEGER, true);
    if (field === 'max_completion_tokens') return requireInteger(value, label, 0, 4_194_304, true);
    if (field === 'agent_max_iterations') return requireInteger(value, label, 1, 1_000_000_000);
    if (field === 'top_logprobs') return requireInteger(value, label, 0, 5, true);
    if (field === 'reasoning_effort') {
        if (value === null) return;
        if (typeof value !== 'string' || !isReasoningEffortLevel(value)) fail(label);
        return;
    }
    if (field === 'service_tier') {
        if (value !== null && (typeof value !== 'string' || !isChatServiceTier(value))) fail(label);
        return;
    }
    if (field === 'stop') {
        const entries = isJsonArray(value) ? value : fail(label);
        if (entries.length > 50) fail(label);
        entries.forEach((entry) => requireString(entry, label, false));
        return;
    }
    if (field === 'top_p') return requireNumber(value, label, 0, 1);
    if (field === 'temperature') return requireNumber(value, label, 0, 2);
    requireNumber(value, label, -2, 2);
};

const validateKnowledge = (field: string, value: JsonValue, label: string): void => {
    if (field === 'enabled') return requireBoolean(value, label);
    if (field === 'retrieval_strategy') return requireEnum(value, label, RETRIEVAL_STRATEGIES);
    if (field === 'chunking_strategy') return requireEnum(value, label, CHUNKING_STRATEGIES);
    if (field === 'top_k') return requireInteger(value, label, 1, 50);
    if (field === 'chunk_size') return requireInteger(value, label, 100, 4_000);
    if (field === 'chunk_overlap') return requireInteger(value, label, 0, 500);
    if (field === 'similarity_threshold') return requireNumber(value, label, 0, 1);
    requireString(value, label, true);
};

const validateSectionField = (section: ChatPresetSectionId, field: string, value: JsonValue): void => {
    const label = `Chat preset ${section}.${field}`;
    if (section === 'general') return validateGeneral(field, value, label);
    if (section === 'appearance') return validateAppearance(field, value, label);
    if (section === 'completion') return validateCompletion(field, value, label);
    if (section === 'voice') return requireString(value, label, false);
    if (section === 'files') return requireString(value, label, true);
    if (section === 'knowledge') return validateKnowledge(field, value, label);
    if (field === 'servers') return requireBooleanMap(value, label);
    if (field === 'modes') return requireToolModes(value, label);
    requireBoolean(value, label);
};

const decodeSection = (section: ChatPresetSectionId, value: JsonValue): JsonObject => {
    const record = requireRecord(value, `Chat preset ${section}`);
    const keys = Object.keys(record);
    if (keys.length === 0 || keys.some((key) => !SECTION_FIELDS[section].includes(key))) fail(`Chat preset ${section}`);
    Object.entries(record).forEach(([field, entry]) => validateSectionField(section, field, entry));
    const chunkingStrategy = record['chunking_strategy'];
    const requiresBoundedOverlap = chunkingStrategy === 'token_based' || chunkingStrategy === 'fixed_size';
    if (section === 'knowledge' && requiresBoundedOverlap && typeof record['chunk_size'] === 'number' && typeof record['chunk_overlap'] === 'number' && record['chunk_overlap'] >= record['chunk_size']) fail('Chat preset knowledge chunk window');
    return { ...record };
};

const decodeChatPresetSections = (value: JsonValue | undefined): ChatPresetSections => {
    const record = requireRecord(value, 'Chat preset sections');
    const sections: ChatPresetSections = {};
    Object.entries(record).forEach(([section, sectionValue]) => {
        if (section === 'general') sections.general = decodeSection(section, sectionValue);
        else if (section === 'appearance') sections.appearance = decodeSection(section, sectionValue);
        else if (section === 'completion') sections.completion = decodeSection(section, sectionValue);
        else if (section === 'voice') sections.voice = decodeSection(section, sectionValue);
        else if (section === 'files') sections.files = decodeSection(section, sectionValue);
        else if (section === 'knowledge') sections.knowledge = decodeSection(section, sectionValue);
        else if (section === 'tools') sections.tools = decodeSection(section, sectionValue);
        else fail('Chat preset sections');
    });
    return sections;
};

const canonicalizeOutboundSection = (section: JsonObject): JsonObject => {
    const canonical: JsonObject = {};
    Object.entries(section).forEach(([field, value]) => {
        canonical[field] = typeof value === 'number' && Object.is(value, -0) ? 0 : value;
    });
    return canonical;
};

const serializeChatPresetSections = (sections: ChatPresetSections): JsonObject => {
    const record: JsonObject = {};
    if (sections.general !== undefined) record['general'] = canonicalizeOutboundSection(sections.general);
    if (sections.appearance !== undefined) record['appearance'] = canonicalizeOutboundSection(sections.appearance);
    if (sections.completion !== undefined) record['completion'] = canonicalizeOutboundSection(sections.completion);
    if (sections.voice !== undefined) record['voice'] = canonicalizeOutboundSection(sections.voice);
    if (sections.files !== undefined) record['files'] = canonicalizeOutboundSection(sections.files);
    if (sections.knowledge !== undefined) record['knowledge'] = canonicalizeOutboundSection(sections.knowledge);
    if (sections.tools !== undefined) record['tools'] = canonicalizeOutboundSection(sections.tools);
    decodeChatPresetSections(record);
    return record;
};

export { SECTION_IDS, decodeChatPresetSections, serializeChatPresetSections };

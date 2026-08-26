/* SoAI - Catalog feature OpenAI capability descriptors [frontend/assets/ts/features/catalog/openaiCapabilityDescriptors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { hasOpenAIModality, isOpenAICapabilityEnabled, normalizeOpenAICapabilityToken, type OpenAICategory } from '@core/openai/capabilityChecks.ts';
import { OPENAI_CAPABILITY_CATEGORIES } from '@core/openai/capabilityCategories.ts';
import type { CapabilityDescriptor } from '@core/openai/protocols.ts';
import { formatTitleFromId } from '@core/primitives/text.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { requireCatalogStore } from '@features/catalog/service.ts';

export type { CapabilityDescriptor };
export type { OpenAICategory };

const OPENAI_CATEGORY_ORDER: ReadonlyArray<OpenAICategory> = OPENAI_CAPABILITY_CATEGORIES.filter((category) => category !== 'responses_features');

const formatCapabilityFallbackLabel = (token: string): string => formatTitleFromId(token);

const getCapabilityManifestSnapshot = (): JsonObject | null => {
    const store = requireCatalogStore();
    const getCapabilityManifest = isObject(store) ? store['getCapabilityManifest'] : null;
    if (!isFunction(getCapabilityManifest)) {
        return null;
    }
    const manifest = getCapabilityManifest();
    return isJsonObject(manifest) ? manifest : null;
};

const resolveOpenAIEndpointDescriptor = (token: string): CapabilityDescriptor => {
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    switch (normalizedToken) {
        case 'chat_completions':
            return { id: 'openai-chat', label: i18n.t('plugins.capabilities.chat'), className: 'capability-openai-chat' };
        case 'completions':
            return { id: 'openai-completions', label: i18n.t('plugins.capabilities.completions'), className: 'capability-openai-completions' };
        case 'responses':
            return { id: 'openai-responses', label: i18n.t('plugins.capabilities.responses'), className: 'capability-openai-responses' };
        case 'embeddings':
            return { id: 'openai-embeddings', label: i18n.t('plugins.capabilities.embeddings'), className: 'capability-openai-embeddings' };
        case 'images':
            return { id: 'openai-images', label: i18n.t('plugins.capabilities.images'), className: 'capability-openai-images' };
        case 'audio_transcriptions':
            return {
                id: 'openai-audio-transcriptions',
                label: i18n.t('plugins.capabilities.audioTranscriptions'),
                className: 'capability-openai-audio-transcriptions'
            };
        case 'audio_translations':
            return {
                id: 'openai-audio-translations',
                label: i18n.t('plugins.capabilities.audioTranslations'),
                className: 'capability-openai-audio-translations'
            };
        case 'audio_speech':
            return { id: 'openai-audio-speech', label: i18n.t('plugins.capabilities.audioSpeech'), className: 'capability-openai-audio-speech' };
        default:
            return {
                id: `openai-endpoints-${normalizedToken}`,
                label: formatCapabilityFallbackLabel(normalizedToken),
                className: 'capability-openai-unknown'
            };
    }
};

const resolveOpenAIImageFeatureDescriptor = (token: string): CapabilityDescriptor => {
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    switch (normalizedToken) {
        case 'image_edits':
            return { id: 'openai-image-edits', label: i18n.t('plugins.capabilities.imageEdits'), className: 'capability-openai-image-edits' };
        case 'image_variations':
            return {
                id: 'openai-image-variations',
                label: i18n.t('plugins.capabilities.imageVariations'),
                className: 'capability-openai-image-variations'
            };
        default:
            return {
                id: `openai-image_features-${normalizedToken}`,
                label: formatCapabilityFallbackLabel(normalizedToken),
                className: 'capability-openai-unknown'
            };
    }
};

const resolveOpenAIChatFeatureDescriptor = (token: string): CapabilityDescriptor => {
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    switch (normalizedToken) {
        case 'vision':
            return { id: 'openai-vision', label: i18n.t('plugins.capabilities.vision'), className: 'capability-openai-vision' };
        case 'input_audio':
            return { id: 'openai-input-audio', label: i18n.t('plugins.capabilities.inputAudio'), className: 'capability-openai-input-audio' };
        case 'tool_calling':
            return { id: 'openai-tool-calling', label: i18n.t('plugins.capabilities.toolCalling'), className: 'capability-openai-tool-calling' };
        case 'parallel_tool_calls':
            return { id: 'openai-parallel-tools', label: i18n.t('plugins.capabilities.parallelToolCalls'), className: 'capability-openai-parallel-tool-calls' };
        case 'structured_output':
            return { id: 'openai-structured-output', label: i18n.t('plugins.capabilities.structuredOutput'), className: 'capability-openai-structured-output' };
        case 'json_schema':
            return { id: 'openai-json-schema', label: i18n.t('plugins.capabilities.jsonSchema'), className: 'capability-openai-json-schema' };
        default:
            return {
                id: `openai-chat_features-${normalizedToken}`,
                label: formatCapabilityFallbackLabel(normalizedToken),
                className: 'capability-openai-unknown'
            };
    }
};

const resolveOpenAIResponsesFeatureDescriptor = (token: string): CapabilityDescriptor => {
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    switch (normalizedToken) {
        case 'create':
            return { id: 'openai-responses-create', label: i18n.t('plugins.capabilities.responsesCreate'), className: 'capability-openai-responses-create' };
        case 'retrieve':
            return { id: 'openai-responses-retrieve', label: i18n.t('plugins.capabilities.responsesRetrieve'), className: 'capability-openai-responses-retrieve' };
        case 'delete':
            return { id: 'openai-responses-delete', label: i18n.t('plugins.capabilities.responsesDelete'), className: 'capability-openai-responses-delete' };
        case 'cancel':
            return { id: 'openai-responses-cancel', label: i18n.t('plugins.capabilities.responsesCancel'), className: 'capability-openai-responses-cancel' };
        case 'input_items':
            return { id: 'openai-responses-input-items', label: i18n.t('plugins.capabilities.responsesInputItems'), className: 'capability-openai-responses-input-items' };
        case 'input_tokens':
            return { id: 'openai-responses-input-tokens', label: i18n.t('plugins.capabilities.responsesInputTokens'), className: 'capability-openai-responses-input-tokens' };
        default:
            return {
                id: `openai-responses_features-${normalizedToken}`,
                label: formatCapabilityFallbackLabel(normalizedToken),
                className: 'capability-openai-unknown'
            };
    }
};

export const resolveOpenAITokenDescriptor = (category: OpenAICategory, token: string): CapabilityDescriptor => {
    switch (category) {
        case 'endpoints':
            return resolveOpenAIEndpointDescriptor(token);
        case 'image_features':
            return resolveOpenAIImageFeatureDescriptor(token);
        case 'chat_features':
            return resolveOpenAIChatFeatureDescriptor(token);
        case 'responses_features':
            return resolveOpenAIResponsesFeatureDescriptor(token);
        default:
            return {
                id: `openai-${category}-${normalizeOpenAICapabilityToken(token)}`,
                label: formatCapabilityFallbackLabel(token),
                className: 'capability-openai-unknown'
            };
    }
};

export const resolveOpenAIModalityDescriptor = (modality: string): CapabilityDescriptor => {
    const normalized = normalizeOpenAICapabilityToken(modality);
    if (normalized === 'text') {
        return { id: 'modality-text', label: i18n.t('plugins.capabilities.modalityText'), className: 'capability-modality-text' };
    }
    if (normalized === 'vision') {
        return { id: 'modality-vision', label: i18n.t('plugins.capabilities.modalityVision'), className: 'capability-modality-vision' };
    }
    if (normalized === 'audio') {
        return { id: 'modality-audio', label: i18n.t('plugins.capabilities.modalityAudio'), className: 'capability-modality-audio' };
    }
    return { id: `modality-${normalized}`, label: formatCapabilityFallbackLabel(normalized), className: `capability-modality-${normalized}` };
};

const collectOpenAIDescriptors = (openai: JsonObject): CapabilityDescriptor[] => {
    if (!isJsonObject(openai)) {
        return [];
    }
    const manifestCandidate = getCapabilityManifestSnapshot();
    if (!manifestCandidate) {
        return [];
    }
    const manifest = manifestCandidate;
    const descriptors: CapabilityDescriptor[] = [];
    const usedIds = new Set<string>();

    for (const category of OPENAI_CATEGORY_ORDER) {
        const manifestCategory = manifest[category];
        const tokens = filterStringArrayValue(manifestCategory);
        for (const token of tokens) {
            if (!isOpenAICapabilityEnabled(openai, category, token)) continue;
            const descriptor = resolveOpenAITokenDescriptor(category, token);
            if (!descriptor || usedIds.has(descriptor.id)) continue;
            descriptors.push(descriptor);
            usedIds.add(descriptor.id);
        }
    }

    const manifestModalities = filterStringArrayValue(manifest['modalities']);
    const modalities = filterStringArrayValue(openai['modalities']);
    for (const modality of modalities) {
        const normalized = normalizeOpenAICapabilityToken(modality);
        if (!normalized) continue;
        if (manifestModalities.length && !manifestModalities.includes(normalized)) continue;
        if (!hasOpenAIModality(modalities, normalized)) continue;
        const descriptor = resolveOpenAIModalityDescriptor(normalized);
        if (usedIds.has(descriptor.id)) continue;
        descriptors.push(descriptor);
        usedIds.add(descriptor.id);
    }

    return descriptors;
};

export const getOpenAIDescriptors = (openai: JsonObject): CapabilityDescriptor[] => collectOpenAIDescriptors(openai);

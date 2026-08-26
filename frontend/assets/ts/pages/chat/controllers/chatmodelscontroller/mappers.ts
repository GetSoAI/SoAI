/* SoAI - Chat page mappers [frontend/assets/ts/pages/chat/controllers/chatmodelscontroller/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { resolveModelDisplayName } from '@core/models/modelRecordNormalization.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { Conversation, ConversationMessage } from '@features/chat/public.ts';

const resolveModelKeyFromCandidate = (candidate: string | null | undefined, models: ModelData[], modelIndex: Map<string, ModelData>, notifyAmbiguousModelSelection: (modelKey: string) => void): string | null => {
    if (!candidate || models.length === 0) {
        return null;
    }
    const key = isString(candidate) ? candidate.trim() : String(candidate);
    if (!key) {
        return null;
    }
    if (modelIndex.has(key)) {
        return key;
    }
    const matches = models.filter((model) => model.id === key || model.name === key);
    if (matches.length === 1) {
        const match = matches[0];
        if (match) {
            return match.id;
        }
    }
    if (matches.length > 1) {
        notifyAmbiguousModelSelection(key);
    }
    return null;
};

const resolveNextModelKey = (models: ModelData[], resolvedKey: string | null): string | null => {
    const hasResolvedModel = resolvedKey && models.some((model) => model.id === resolvedKey);
    if (hasResolvedModel && resolvedKey) {
        return resolvedKey;
    }
    const loadedModel = models.find((model) => model.loaded === true && isChatSelectableModel(model));
    if (loadedModel) {
        return loadedModel.id;
    }
    const availableModel = models.find((model) => model.available === true && isChatSelectableModel(model));
    if (availableModel) {
        return availableModel.id;
    }
    return null;
};

const resolveAssistantLabel = (conversation: Conversation, message: ConversationMessage, modelIndex: Map<string, ModelData>, currentModel: string | null, modelStreamHasPayload: boolean): string => {
    const messageModelIdValue = message.modelId;
    const messageModelId = toTrimmedStringOrNull(messageModelIdValue);
    const convModelValue = conversation.modelSettings.model;
    const convModelId = toTrimmedStringOrNull(convModelValue);
    let preferredModelId: string | null = null;
    if (messageModelId) {
        preferredModelId = messageModelId;
    } else if (convModelId) {
        preferredModelId = convModelId;
    } else {
        preferredModelId = toTrimmedStringOrNull(currentModel);
    }
    const label = resolveModelDisplayName(modelIndex, preferredModelId);
    if (!label) {
        return i18n.t('chat.message.assistant');
    }
    const normalizedPreferred = toTrimmedStringOrNull(preferredModelId);
    if (modelStreamHasPayload && normalizedPreferred && !modelIndex.has(normalizedPreferred)) {
        const suffix = i18n.t('chat.modelControl.missingSuffix').trim();
        if (suffix && !label.endsWith(suffix)) {
            return `${label} ${suffix}`.trim();
        }
    }
    return label;
};

const conversationRequiresAssistantLabelRerender = (conversation: Conversation, previousModelIndex: Map<string, ModelData>, previousCurrentModel: string | null, previousModelStreamHasPayload: boolean, nextModelIndex: Map<string, ModelData>, nextCurrentModel: string | null, nextModelStreamHasPayload: boolean): boolean => {
    const visibleMessages = conversation.messages.filter((message) => message?.role !== 'system');
    if (visibleMessages.length === 0) {
        return false;
    }
    return visibleMessages.some((message) => {
        if (message?.role !== 'assistant') {
            return false;
        }
        const prevLabel = resolveAssistantLabel(conversation, message, previousModelIndex, previousCurrentModel, previousModelStreamHasPayload);
        const nextLabel = resolveAssistantLabel(conversation, message, nextModelIndex, nextCurrentModel, nextModelStreamHasPayload);
        return prevLabel !== nextLabel;
    });
};

export { conversationRequiresAssistantLabelRerender, resolveModelKeyFromCandidate, resolveNextModelKey };

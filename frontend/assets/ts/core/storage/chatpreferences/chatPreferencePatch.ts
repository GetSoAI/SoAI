/* SoAI - Authoritative chat preference patch partitioning [frontend/assets/ts/core/storage/chatpreferences/chatPreferencePatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneJsonObject } from '@core/primitives/clone.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

const decodeAuthoritativeConversationDefaults = (response: JsonObject): JsonObject => {
    const chat = response['chat'];
    const defaults = isJsonObject(chat) ? chat['conversation_defaults_v1'] : undefined;
    if (defaults === undefined) return {};
    if (!isJsonObject(defaults) || defaults['version'] !== 1 || Object.keys(defaults).some((key) => key !== 'version' && key !== 'model_settings' && key !== 'rag_config')) throw new Error('Authoritative conversation defaults are invalid.');
    const modelSettings = defaults['model_settings'];
    if (modelSettings === undefined) return {};
    if (!isJsonObject(modelSettings)) throw new Error('Authoritative conversation default model settings are invalid.');
    return cloneJsonObject(modelSettings);
};

const partitionChatPreferencePatch = (chatPatch: JsonObject): Readonly<{ chatDelta: JsonObject; conversationDefaultsDelta: JsonObject }> => {
    const chatDelta = cloneJsonObject(chatPatch);
    const defaults = chatDelta['conversation_defaults_v1'];
    delete chatDelta['conversation_defaults_v1'];
    if (defaults === undefined) return { chatDelta, conversationDefaultsDelta: {} };
    if (!isJsonObject(defaults) || defaults['version'] !== 1 || Object.keys(defaults).some((key) => key !== 'version' && key !== 'model_settings') || !isJsonObject(defaults['model_settings'])) {
        throw new Error('Conversation default preference patch is invalid.');
    }
    return { chatDelta, conversationDefaultsDelta: cloneJsonObject(defaults['model_settings']) };
};

const combineChatPreferencePatch = (chatDelta: JsonObject, conversationDefaultsDelta: JsonObject): JsonObject => {
    const chat = cloneJsonObject(chatDelta);
    if (Object.keys(conversationDefaultsDelta).length > 0) chat['conversation_defaults_v1'] = { version: 1, 'model_settings': cloneJsonObject(conversationDefaultsDelta) };
    return Object.keys(chat).length > 0 ? { chat } : {};
};

export { combineChatPreferencePatch, decodeAuthoritativeConversationDefaults, partitionChatPreferencePatch };

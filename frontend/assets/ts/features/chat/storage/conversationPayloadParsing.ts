/* SoAI - Chat feature conversation payload parsing [frontend/assets/ts/features/chat/storage/conversationPayloadParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isArray, isBoolean, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { isEpochMsValue } from '@core/time/epochMs.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveConversationDisplayTitleFromConversation } from '@features/chat/conversationFormatting.ts';
import { mergeModelSettingsPatch, parseRequiredModelSettings, requireBackendConversationTitle, requireConversationBoolean, requireConversationColor, requireConversationModelSettings, requireConversationTitle, requireEpochMs, requireNonNegativeNumber } from '@features/chat/storage/conversationPayloadFields.ts';
import type { ArchivedConversationSummary, ArchivedConversationsCursor, ArchivedConversationsPage, Conversation } from '@features/chat/storage/storageModels.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import type { ArchivedConversationsPageResponse, ArchivedConversationResponse, WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import type { ConversationUpdatedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';

type ConversationPatch = {
    updatedAt: number;
    messageCount?: number;
    title?: string;
    isFavorite?: boolean;
    color?: string | null;
    modelSettings?: Conversation['modelSettings'];
    isArchived?: boolean;
    settingsAuthorityChanged?: boolean;
};

const parseBackendConversationRecord = (value: WebuiConversationResponse, options: { context?: string; messagesHydrated?: boolean } = {}): Conversation => {
    const context = options.context ?? 'Backend conversation';
    return {
        id: requireConversationId(value.id, context),
        title: requireBackendConversationTitle(value.title, context),
        messages: [],
        messagesHydrated: options.messagesHydrated === true,
        createdAt: requireEpochMs(value.createdAtMs, 'created_at_ms', context),
        updatedAt: requireEpochMs(value.lastModifiedAtMs, 'last_modified_at_ms', context),
        modelSettings: parseRequiredModelSettings(value.modelSettings, context),
        isFavorite: requireConversationBoolean(value.isFavorite, 'is_favorite', context),
        color: requireConversationColor(value.color, context),
        isAutomation: requireConversationBoolean(value.isAutomation, 'is_automation', context),
        isMessaging: requireConversationBoolean(value.isMessaging, 'is_messaging', context),
        messagingPlatform: value.messagingPlatform,
        messagingAccountLabel: value.messagingAccountLabel,
        messagingAccountSnapshotId: value.messagingAccountSnapshotId,
        isArchived: value.isArchived,
        messageCount: requireNonNegativeNumber(value.messageCount, 'message_count', context),
        compactionCount: requireNonNegativeNumber(value.compactionCount, 'compaction_count', context),
        compactionTokensSaved: requireNonNegativeNumber(value.compactionTokensSaved, 'compaction_tokens_saved', context),
        settingsAuthority: value.settingsAuthority
    };
};

const parseBackendConversationList = (value: readonly WebuiConversationResponse[], options: { context?: string; messagesHydrated?: boolean } = {}): Map<string, Conversation> => {
    const context = options.context ?? 'Backend conversation list';
    const conversations = new Map<string, Conversation>();
    for (let index = 0; index < value.length; index += 1) {
        const entry = value[index];
        if (!entry) {
            throw new Error(`${context}[${String(index)}] is missing`);
        }
        const recordOptions: { context: string; messagesHydrated?: boolean } = {
            context: `${context}[${String(index)}]`
        };
        if (options.messagesHydrated !== undefined) {
            recordOptions.messagesHydrated = options.messagesHydrated;
        }
        const conversation = parseBackendConversationRecord(entry, recordOptions);
        if (conversations.has(conversation.id)) {
            throw new Error(`${context} contains duplicate conversation id ${conversation.id}`);
        }
        conversations.set(conversation.id, conversation);
    }
    return conversations;
};

const isPersistableConversation = (value: ConversationContract): value is Conversation => {
    if (!isString(value.id) || value.id.trim().length === 0) {
        return false;
    }
    if (!isString(value.title) || value.title.trim().length === 0) {
        return false;
    }
    if (!isArray(value.messages)) {
        return false;
    }
    if (!isNumber(value.createdAt) || !isEpochMsValue(value.createdAt)) {
        return false;
    }
    if (!isNumber(value.updatedAt) || !isEpochMsValue(value.updatedAt)) {
        return false;
    }
    if (!isPlainObject(value.modelSettings)) {
        return false;
    }
    if (!isBoolean(value.isFavorite)) {
        return false;
    }
    if (value.color !== null && !isString(value.color)) {
        return false;
    }
    if (!isBoolean(value.isAutomation)) {
        return false;
    }
    if (!isBoolean(value.isMessaging)) {
        return false;
    }
    if (!isBoolean(value.isArchived)) {
        return false;
    }
    if (!isPlainObject(value.settingsAuthority)) {
        return false;
    }
    const messageCountValue = value.messageCount;
    return isNumber(messageCountValue) && Number.isInteger(messageCountValue) && messageCountValue >= 0;
};

const requirePersistableConversation = (value: ConversationContract | null): Conversation => {
    const context = 'Conversation';
    if (!value || !isPlainObject(value)) {
        throw new Error(`${context} is required for backend synchronization`);
    }
    const messagesValue = value.messages;
    if (!isArray(messagesValue)) {
        throw new Error(`${context} messages must be an array`);
    }
    const title = resolveConversationDisplayTitleFromConversation(value, i18n.t('chat.conversation.untitled'));
    const messageCountValue = value.messageCount;
    const messageCount = isNumber(messageCountValue) ? requireNonNegativeNumber(messageCountValue, 'message_count', context) : messagesValue.length;
    value.id = requireConversationId(value.id, context);
    value.title = requireConversationTitle(title, context);
    value.messages = messagesValue;
    value.createdAt = requireEpochMs(value.createdAt, 'created_at', context);
    value.updatedAt = requireEpochMs(value.updatedAt, 'updated_at', context);
    value.modelSettings = requireConversationModelSettings(value.modelSettings, context);
    value.isFavorite = requireConversationBoolean(value.isFavorite, 'is_favorite', context);
    value.color = requireConversationColor(value.color, context);
    value.isAutomation = requireConversationBoolean(value.isAutomation, 'is_automation', context);
    value.isMessaging = requireConversationBoolean(value.isMessaging, 'is_messaging', context);
    value.isArchived = requireConversationBoolean(value.isArchived, 'is_archived', context);
    if (!isPlainObject(value.settingsAuthority)) {
        throw new Error(`${context} settings authority is missing or invalid`);
    }
    value.messageCount = messageCount;
    if (!isPersistableConversation(value)) {
        throw new Error(`${context} normalized payload is invalid`);
    }
    return value;
};

const parseBackendConversationUpdateEvent = (value: ConversationUpdatedEvent, currentSettings: Conversation['modelSettings']): { conversationId: string; patch: ConversationPatch } => {
    const context = 'Conversation update event payload';
    const patch: ConversationPatch = { updatedAt: value.lastModifiedAtMs, settingsAuthorityChanged: value.settingsAuthorityChanged };
    if (value.title !== undefined) patch.title = value.title;
    if (value.isFavorite !== undefined) patch.isFavorite = value.isFavorite;
    if (value.color !== undefined) patch.color = value.color;
    if (value.modelSettings !== undefined) patch.modelSettings = mergeModelSettingsPatch(currentSettings, value.modelSettings, context);
    if (value.isArchived !== undefined) patch.isArchived = value.isArchived;
    if (value.messageCount !== undefined) patch.messageCount = value.messageCount;
    return {
        conversationId: value.convId,
        patch
    };
};

const parseArchivedConversationSummary = (value: ArchivedConversationResponse, context: string): ArchivedConversationSummary => {
    return {
        id: requireConversationId(value.id, context),
        title: requireBackendConversationTitle(value.title, context),
        updatedAt: requireEpochMs(value.lastModifiedAtMs, 'last_modified_at_ms', context),
        color: requireConversationColor(value.color, context),
        isFavorite: requireConversationBoolean(value.isFavorite, 'is_favorite', context),
        isAutomation: requireConversationBoolean(value.isAutomation, 'is_automation', context),
        isMessaging: requireConversationBoolean(value.isMessaging, 'is_messaging', context),
        messagingPlatform: value.messagingPlatform,
        messagingAccountLabel: value.messagingAccountLabel,
        messagingAccountSnapshotId: value.messagingAccountSnapshotId,
        isArchived: requireConversationBoolean(value.isArchived, 'is_archived', context),
        settingsAuthority: value.settingsAuthority,
        messageCount: requireNonNegativeNumber(value.messageCount, 'message_count', context),
        compactionCount: requireNonNegativeNumber(value.compactionCount, 'compaction_count', context),
        compactionTokensSaved: requireNonNegativeNumber(value.compactionTokensSaved, 'compaction_tokens_saved', context)
    };
};

const parseArchivedConversationsCursor = (value: ArchivedConversationsPageResponse['nextCursor'], context: string): ArchivedConversationsCursor | null => {
    if (value === null) {
        return null;
    }
    return {
        lastModifiedAtMs: requireEpochMs(value.lastModifiedAtMs, 'last_modified_at_ms', `${context} next_cursor`),
        id: requireConversationId(value.id, `${context} next_cursor`)
    };
};

const parseArchivedConversationsPage = (value: ArchivedConversationsPageResponse, context = 'Archived conversations response'): ArchivedConversationsPage => {
    return {
        conversations: value.conversations.map((entry, index) => parseArchivedConversationSummary(entry, `${context} conversations[${String(index)}]`)),
        totalCount: requireNonNegativeNumber(value.totalCount, 'total_count', context),
        nextCursor: parseArchivedConversationsCursor(value.nextCursor, context)
    };
};

const parseArchivedConversationSearchResponse = (value: readonly ArchivedConversationResponse[], context = 'Archived conversation search response'): ArchivedConversationSummary[] => {
    return value.map((entry, index) => parseArchivedConversationSummary(entry, `${context} conversations[${String(index)}]`));
};

export { parseArchivedConversationSearchResponse, parseArchivedConversationsPage, parseBackendConversationList, parseBackendConversationRecord, parseBackendConversationUpdateEvent, requireConversationBoolean, requireConversationColor, requireConversationModelSettings, requireConversationTitle, requireEpochMs, parseRequiredModelSettings, requirePersistableConversation };

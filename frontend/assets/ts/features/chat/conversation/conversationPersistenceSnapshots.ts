/* SoAI - Chat feature conversation persistence snapshots [frontend/assets/ts/features/chat/conversation/conversationPersistenceSnapshots.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPlainObject } from '@core/typeGuards.ts';
import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import { parseBackendConversationRecord, requireConversationBoolean, requireConversationColor, requireConversationModelSettings, requireConversationTitle } from '@features/chat/storage/conversationPayloadParsing.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { serializeConversationModelSettings } from '@core/chat/executionSettingsMapping.ts';
import type { ConversationCreateRequest } from '@core/api/contracts/webuiConversationRequestContracts.ts';

type ConversationPersistenceSnapshot = {
    id: string;
    title: string;
    modelSettings: Conversation['modelSettings'];
    color: string | null;
    isFavorite: boolean;
};

const requireConversationPersistenceSnapshot = (conversation: Conversation): ConversationPersistenceSnapshot => {
    if (!isPlainObject(conversation)) {
        throw new Error('Conversation is missing or invalid');
    }
    return {
        id: requireConversationId(conversation.id, 'Conversation'),
        title: requireConversationTitle(conversation.title, 'Conversation'),
        modelSettings: requireConversationModelSettings(conversation.modelSettings, 'Conversation'),
        color: requireConversationColor(conversation.color, 'Conversation'),
        isFavorite: requireConversationBoolean(conversation.isFavorite, 'is_favorite', 'Conversation')
    };
};

const buildConversationCreatePayload = (conversation: { id: string; title: string }): ConversationCreateRequest => {
    return {
        id: conversation.id,
        title: conversation.title
    };
};

const requireConversationStateEntry = (conversations: Map<string, Conversation>, conversationId: string): Conversation => {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
        throw new Error(`Conversation not found: ${conversationId}`);
    }
    return conversation;
};

const parseConversationRecordForId = (value: WebuiConversationResponse, requestedConversationId: string, context: string): Conversation => {
    const conversation = parseBackendConversationRecord(value, {
        context,
        messagesHydrated: true
    });
    if (conversation.id !== requestedConversationId) {
        throw new Error(`${context} id does not match requested conversation ${requestedConversationId}`);
    }
    return conversation;
};

const parseCreatedConversationRecord = (value: WebuiConversationResponse, requestedConversationId: string, requestedTitle: string): Conversation => {
    const conversation = parseConversationRecordForId(value, requestedConversationId, 'Created conversation payload');
    if (conversation.title !== requestedTitle) {
        throw new Error(`Created conversation payload title does not match requested conversation ${requestedConversationId}`);
    }
    return conversation;
};

const applyConversationMetadataSnapshot = (target: Conversation, snapshot: Conversation): boolean => {
    if (snapshot.updatedAt < target.updatedAt) {
        return false;
    }
    target.createdAt = snapshot.createdAt;
    target.updatedAt = snapshot.updatedAt;
    target.title = snapshot.title;
    target.color = snapshot.color;
    target.isFavorite = snapshot.isFavorite;
    target.isAutomation = snapshot.isAutomation === true;
    target.isMessaging = snapshot.isMessaging === true;
    target.messagingPlatform = snapshot.messagingPlatform ?? null;
    target.messagingAccountLabel = snapshot.messagingAccountLabel ?? null;
    target.messagingAccountSnapshotId = snapshot.messagingAccountSnapshotId ?? null;
    if (snapshot.settingsAuthority) target.settingsAuthority = snapshot.settingsAuthority;
    else delete target.settingsAuthority;
    target.isArchived = snapshot.isArchived === true;
    return true;
};

const applyConversationSettingsSnapshot = (target: Conversation, snapshot: Conversation): void => {
    if (applyConversationMetadataSnapshot(target, snapshot)) {
        target.modelSettings = snapshot.modelSettings;
    }
};

const reconcilePersistedConversationSnapshot = (target: Conversation, snapshot: ConversationPersistenceSnapshot, persisted: Conversation): void => {
    const shouldApplyTitle = target.title === snapshot.title;
    const shouldApplyColor = target.color === snapshot.color;
    const shouldApplyFavorite = target.isFavorite === snapshot.isFavorite;
    const shouldApplyModelSettings = compareParameterValues(serializeConversationModelSettings(target.modelSettings), serializeConversationModelSettings(snapshot.modelSettings));
    target.createdAt = persisted.createdAt;
    target.isAutomation = persisted.isAutomation === true;
    target.isMessaging = persisted.isMessaging === true;
    target.messagingPlatform = persisted.messagingPlatform ?? null;
    target.messagingAccountLabel = persisted.messagingAccountLabel ?? null;
    target.messagingAccountSnapshotId = persisted.messagingAccountSnapshotId ?? null;
    if (persisted.settingsAuthority) target.settingsAuthority = persisted.settingsAuthority;
    else delete target.settingsAuthority;
    target.isArchived = persisted.isArchived === true;
    if (shouldApplyTitle) {
        target.title = persisted.title;
    }
    if (shouldApplyColor) {
        target.color = persisted.color;
    }
    if (shouldApplyFavorite) {
        target.isFavorite = persisted.isFavorite;
    }
    if (shouldApplyModelSettings) {
        target.modelSettings = persisted.modelSettings;
    }
    if (shouldApplyTitle && shouldApplyColor && shouldApplyFavorite && shouldApplyModelSettings) {
        target.updatedAt = Math.max(target.updatedAt, persisted.updatedAt);
    }
};

export { applyConversationMetadataSnapshot, applyConversationSettingsSnapshot, buildConversationCreatePayload, parseConversationRecordForId, parseCreatedConversationRecord, reconcilePersistedConversationSnapshot, requireConversationPersistenceSnapshot, requireConversationStateEntry };
export type { ConversationPersistenceSnapshot };

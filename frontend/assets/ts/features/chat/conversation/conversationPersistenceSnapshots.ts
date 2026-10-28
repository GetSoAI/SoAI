/* SoAI - Chat feature conversation persistence snapshots [frontend/assets/ts/features/chat/conversation/conversationPersistenceSnapshots.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject } from '@core/types/jsonValues.ts';
import { resolveMessageTitle } from '@features/chat/messageBuilding.ts';
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
    titleAutoUpdateAllowed?: boolean;
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
        ...(conversation.titleAutoUpdateAllowed === undefined ? {} : { titleAutoUpdateAllowed: requireConversationBoolean(conversation.titleAutoUpdateAllowed, 'title_auto_update_allowed', 'Conversation') }),
        modelSettings: requireConversationModelSettings(conversation.modelSettings, 'Conversation'),
        color: requireConversationColor(conversation.color, 'Conversation'),
        isFavorite: requireConversationBoolean(conversation.isFavorite, 'is_favorite', 'Conversation')
    };
};

const buildConversationCreatePayload = (conversation: { id: string; title: string; titleAutoUpdateAllowed?: boolean }): ConversationCreateRequest => {
    return {
        id: conversation.id,
        title: conversation.title,
        ...(conversation.titleAutoUpdateAllowed === undefined ? {} : { titleAutoUpdateAllowed: conversation.titleAutoUpdateAllowed })
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

type ConversationTitleMetadataPatch = { updatedAt: number; title?: string; titleAutoUpdateAllowed?: boolean };

const applyConversationTitleMetadata = (target: Conversation, patch: ConversationTitleMetadataPatch): boolean => {
    if (patch.title === undefined && patch.titleAutoUpdateAllowed === undefined) return false;
    const observed = target.committedTitleMetadata;
    const observedAt = observed?.updatedAt ?? target.updatedAt;
    const observedTitle = observed?.title ?? target.title;
    const observedAuthority = observed?.autoUpdateAllowed ?? target.titleAutoUpdateAllowed;
    if (patch.updatedAt < observedAt) {
        if (observedAuthority !== undefined || patch.titleAutoUpdateAllowed !== undefined || patch.title === undefined) return false;
        const firstUserMessage = target.messages.find((message) => isJsonObject(message) && message['role'] === 'user');
        const defaultTitle = firstUserMessage ? resolveMessageTitle(firstUserMessage) : null;
        if (observedTitle !== patch.title && (defaultTitle === null || observedTitle !== defaultTitle)) return false;
    }
    if (observed && patch.updatedAt === observedAt && ((patch.title !== undefined && patch.title !== observedTitle) || (patch.titleAutoUpdateAllowed !== undefined && observedAuthority !== undefined && patch.titleAutoUpdateAllowed !== observedAuthority))) {
        throw new Error('Conflicting conversation title metadata at the same committed timestamp');
    }
    const title = patch.title ?? observedTitle;
    const autoUpdateAllowed = patch.titleAutoUpdateAllowed ?? observedAuthority;
    target.title = title;
    if (autoUpdateAllowed !== undefined) target.titleAutoUpdateAllowed = autoUpdateAllowed;
    target.committedTitleMetadata = { title, updatedAt: patch.updatedAt, ...(autoUpdateAllowed === undefined ? {} : { autoUpdateAllowed }) };
    target.updatedAt = Math.max(target.updatedAt, patch.updatedAt);
    return true;
};

const applyConversationSnapshotTitleMetadata = (target: Conversation, snapshot: Conversation): boolean =>
    applyConversationTitleMetadata(target, {
        title: snapshot.title,
        updatedAt: snapshot.committedTitleMetadata?.updatedAt ?? snapshot.updatedAt,
        ...(snapshot.titleAutoUpdateAllowed === undefined ? {} : { titleAutoUpdateAllowed: snapshot.titleAutoUpdateAllowed })
    });

const applyConversationMetadataSnapshot = (target: Conversation, snapshot: Conversation): boolean => {
    const previousUpdatedAt = target.updatedAt;
    applyConversationSnapshotTitleMetadata(target, snapshot);
    if (snapshot.updatedAt < previousUpdatedAt) {
        return false;
    }
    target.createdAt = snapshot.createdAt;
    target.updatedAt = snapshot.updatedAt;
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
    const shouldApplyTitle = target.title === snapshot.title && target.titleAutoUpdateAllowed === snapshot.titleAutoUpdateAllowed;
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
        applyConversationSnapshotTitleMetadata(target, persisted);
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

export { applyConversationTitleMetadata, applyConversationSnapshotTitleMetadata, applyConversationMetadataSnapshot, applyConversationSettingsSnapshot, buildConversationCreatePayload, parseConversationRecordForId, parseCreatedConversationRecord, reconcilePersistedConversationSnapshot, requireConversationPersistenceSnapshot, requireConversationStateEntry };
export type { ConversationPersistenceSnapshot };

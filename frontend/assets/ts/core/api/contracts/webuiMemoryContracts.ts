/* SoAI - Frontend WebUI memory contracts [frontend/assets/ts/core/api/contracts/webuiMemoryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiQueryParameters } from '@core/api/types/request.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredBooleanValue, readRequiredEpochMsValue, readRequiredNonEmptyStringValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { isJsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface ChatMemoryEntity {
    name: string;
    entityType: string;
    createdAtMs: number;
    updatedAtMs: number;
}

interface ChatMemoryObservation {
    id: string;
    content: string;
    source: string | null;
    createdAtMs: number;
}

interface ChatMemoryRelation {
    id: string;
    relationType: string;
    toEntity: string | null;
    fromEntity: string | null;
    createdAtMs: number;
}

interface ChatMemoryEntry {
    entity: ChatMemoryEntity;
    observations: ChatMemoryObservation[];
    relations: ChatMemoryRelation[];
}

interface ChatMemoryProfile {
    preferredName: string | null;
    assistantName: string | null;
    roleBackground: string | null;
    currentGoals: string | null;
    preferences: string | null;
    dislikesToAvoid: string | null;
    communicationStyle: string | null;
    recurringToolsProjects: string | null;
    extraNotes: string | null;
}

interface ChatMemorySnapshot {
    entries: ChatMemoryEntry[];
    profileForm: ChatMemoryProfile;
}

type ChatMemoryProfileUpdateRequest = Partial<ChatMemoryProfile> & { expectedRevision?: string };

const readNullableString = (value: JsonValue | undefined, label: string): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredStringValue(value, label);
};

const decodeMemoryEntity = (value: JsonValue | undefined, label: string): ChatMemoryEntity => {
    const record = requireRecord(value, label);
    return {
        name: readRequiredStringValue(record['name'], `${label}.name`),
        entityType: readRequiredStringValue(record['entity_type'], `${label}.entity_type`),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`),
        updatedAtMs: readRequiredEpochMsValue(record['updated_at_ms'], `${label}.updated_at_ms`)
    };
};

const decodeMemoryObservation = (value: JsonValue, label: string): ChatMemoryObservation => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedStringValue(record['id'], `${label}.id`),
        content: readRequiredStringValue(record['content'], `${label}.content`),
        source: readNullableString(record['source'], `${label}.source`),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`)
    };
};

const decodeMemoryRelation = (value: JsonValue, label: string): ChatMemoryRelation => {
    const record = requireRecord(value, label);
    const toEntity = readNullableString(record['to_entity'], `${label}.to_entity`);
    const fromEntity = readNullableString(record['from_entity'], `${label}.from_entity`);
    if ((toEntity === null) === (fromEntity === null)) {
        throw new Error(`${label} must identify exactly one related entity.`);
    }
    return {
        id: readRequiredTrimmedStringValue(record['id'], `${label}.id`),
        relationType: readRequiredStringValue(record['relation_type'], `${label}.relation_type`),
        toEntity,
        fromEntity,
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`)
    };
};

const decodeMemoryEntry = (value: JsonValue, label: string): ChatMemoryEntry => {
    const record = requireRecord(value, label);
    const observations = record['observations'];
    const relations = record['relations'];
    if (!isJsonArray(observations)) {
        throw new Error(`${label}.observations must be an array.`);
    }
    if (!isJsonArray(relations)) {
        throw new Error(`${label}.relations must be an array.`);
    }
    return {
        entity: decodeMemoryEntity(record['entity'], `${label}.entity`),
        observations: observations.map((observation, index) => decodeMemoryObservation(observation, `${label}.observations[${String(index)}]`)),
        relations: relations.map((relation, index) => decodeMemoryRelation(relation, `${label}.relations[${String(index)}]`))
    };
};

const decodeMemoryProfile = (value: JsonValue | undefined, label: string): ChatMemoryProfile => {
    const record = requireRecord(value, label);
    return {
        preferredName: readNullableString(record['preferred_name'], `${label}.preferred_name`),
        assistantName: readNullableString(record['assistant_name'], `${label}.assistant_name`),
        roleBackground: readNullableString(record['role_background'], `${label}.role_background`),
        currentGoals: readNullableString(record['current_goals'], `${label}.current_goals`),
        preferences: readNullableString(record['preferences'], `${label}.preferences`),
        dislikesToAvoid: readNullableString(record['dislikes_to_avoid'], `${label}.dislikes_to_avoid`),
        communicationStyle: readNullableString(record['communication_style'], `${label}.communication_style`),
        recurringToolsProjects: readNullableString(record['recurring_tools_projects'], `${label}.recurring_tools_projects`),
        extraNotes: readNullableString(record['extra_notes'], `${label}.extra_notes`)
    };
};

const decodeChatMemorySnapshot = (value: ApiResponsePayload): ChatMemorySnapshot => {
    const record = requireRecord(value, 'Chat memory snapshot');
    const entries = record['entries'];
    if (!isJsonArray(entries)) {
        throw new Error('Chat memory snapshot.entries must be an array.');
    }
    return {
        entries: entries.map((entry, index) => decodeMemoryEntry(entry, `Chat memory snapshot.entries[${String(index)}]`)),
        profileForm: decodeMemoryProfile(record['profile_form'], 'Chat memory snapshot.profile_form')
    };
};

const serializeChatMemoryProfileUpdate = (request: ChatMemoryProfileUpdateRequest): JsonObject => ({
    ...(request.preferredName === undefined ? {} : { 'preferred_name': request.preferredName }),
    ...(request.assistantName === undefined ? {} : { 'assistant_name': request.assistantName }),
    ...(request.roleBackground === undefined ? {} : { 'role_background': request.roleBackground }),
    ...(request.currentGoals === undefined ? {} : { 'current_goals': request.currentGoals }),
    ...(request.preferences === undefined ? {} : { preferences: request.preferences }),
    ...(request.dislikesToAvoid === undefined ? {} : { 'dislikes_to_avoid': request.dislikesToAvoid }),
    ...(request.communicationStyle === undefined ? {} : { 'communication_style': request.communicationStyle }),
    ...(request.recurringToolsProjects === undefined ? {} : { 'recurring_tools_projects': request.recurringToolsProjects }),
    ...(request.extraNotes === undefined ? {} : { 'extra_notes': request.extraNotes }),
    ...(request.expectedRevision === undefined ? {} : { 'expected_revision': request.expectedRevision })
});

export { decodeChatMemorySnapshot, serializeChatMemoryProfileUpdate };
export type { ChatMemoryEntry, ChatMemoryProfile, ChatMemoryProfileUpdateRequest, ChatMemorySnapshot };

interface ManagedMemoryEntry {
    entity: ChatMemoryEntity & { id: string };
    observations: Array<ChatMemoryObservation & { profileField: string | null }>;
    relations: Array<ChatMemoryRelation & { fromEntityId: string; toEntityId: string; fromEntity: string; toEntity: string }>;
    revision: string;
    isProfile: boolean;
}

interface MemoryLibrary {
    entries: ManagedMemoryEntry[];
    profileForm: ChatMemoryProfile;
    profileRevision: string;
}

interface MemoryEntryUpdate {
    expectedRevision: string;
    name?: string;
    observation?: { id: string | null; content: string };
}

interface MemoryRelationUpdate {
    expectedRevision: string;
    fromEntityId: string;
    toEntityId: string;
    relationType: string;
}

const decodeManagedMemoryEntry = (value: ApiResponsePayload, label = 'Memory entry'): ManagedMemoryEntry => {
    const record = requireRecord(value, label);
    const entity = requireRecord(record['entity'], `${label}.entity`);
    const observations = record['observations'];
    const relations = record['relations'];
    if (!isJsonArray(observations) || !isJsonArray(relations)) throw new Error(`${label} requires observations and relations.`);
    return {
        entity: { ...decodeMemoryEntity(entity, `${label}.entity`), id: readRequiredNonEmptyStringValue(entity['id'], `${label}.entity.id`) },
        observations: observations.map((value, index) => {
            const observation = requireRecord(value, `${label}.observations[${String(index)}]`);
            return { ...decodeMemoryObservation(value, `${label}.observations[${String(index)}]`), id: readRequiredNonEmptyStringValue(observation['id'], `${label}.observation.id`), profileField: readNullableString(observation['profile_field'], `${label}.profile_field`) };
        }),
        relations: relations.map((value, index) => {
            const relation = requireRecord(value, `${label}.relations[${String(index)}]`);
            return {
                id: readRequiredNonEmptyStringValue(relation['id'], `${label}.relation.id`),
                relationType: readRequiredTrimmedStringValue(relation['relation_type'], `${label}.relation.relation_type`),
                fromEntityId: readRequiredNonEmptyStringValue(relation['from_entity_id'], `${label}.relation.from_entity_id`),
                toEntityId: readRequiredNonEmptyStringValue(relation['to_entity_id'], `${label}.relation.to_entity_id`),
                fromEntity: readRequiredStringValue(relation['from_entity'], `${label}.relation.from_entity`),
                toEntity: readRequiredStringValue(relation['to_entity'], `${label}.relation.to_entity`),
                createdAtMs: readRequiredEpochMsValue(relation['created_at_ms'], `${label}.relation.created_at_ms`)
            };
        }),
        revision: readRequiredTrimmedStringValue(record['revision'], `${label}.revision`),
        isProfile: readRequiredBooleanValue(record['is_profile'], `${label}.is_profile`)
    };
};

const decodeMemoryLibrary = (value: ApiResponsePayload): MemoryLibrary => {
    const record = requireRecord(value, 'Memory library');
    const entries = record['entries'];
    if (!isJsonArray(entries)) throw new Error('Memory library.entries must be an array.');
    return {
        entries: entries.map((entry) => decodeManagedMemoryEntry(entry)),
        profileForm: decodeMemoryProfile(record['profile_form'], 'Memory library.profile_form'),
        profileRevision: readRequiredTrimmedStringValue(record['profile_revision'], 'Memory library.profile_revision')
    };
};

export { decodeManagedMemoryEntry, decodeMemoryLibrary };
export type { ManagedMemoryEntry, MemoryLibrary, MemoryEntryUpdate, MemoryRelationUpdate };

const serializeMemoryEntryCreate = (id: string, name: string, content: string): JsonObject => ({ id, name, content });

const serializeMemoryEntryUpdate = (request: MemoryEntryUpdate): JsonObject => ({
    'expected_revision': request.expectedRevision,
    ...(request.name === undefined ? {} : { name: request.name }),
    ...(request.observation === undefined ? {} : { observation: { id: request.observation.id, content: request.observation.content } })
});

const serializeMemoryRelationUpdate = (request: MemoryRelationUpdate): JsonObject => ({
    'expected_revision': request.expectedRevision,
    'from_entity_id': request.fromEntityId,
    'to_entity_id': request.toEntityId,
    'relation_type': request.relationType
});

const serializeMemoryRevisionQuery = (expectedRevision: string): ApiQueryParameters => ({ 'expected_revision': expectedRevision });

const decodeMemoryDeletionResponse = (value: ApiResponsePayload): void => {
    const record = requireRecord(value, 'Memory deletion');
    for (const field of ['entities_deleted', 'observations_deleted_direct', 'observations_deleted_cascade', 'observations_deleted_total', 'relations_deleted_direct', 'relations_deleted_cascade', 'relations_deleted_total', 'records_deleted_total']) {
        readRequiredNonNegativeIntegerValue(record[field], `Memory deletion.${field}`);
    }
};

export { serializeMemoryEntryCreate, serializeMemoryEntryUpdate, serializeMemoryRelationUpdate, serializeMemoryRevisionQuery, decodeMemoryDeletionResponse };

/* SoAI - Frontend WebUI memory contracts [frontend/assets/ts/core/api/contracts/webuiMemoryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredEpochMsValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
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

type ChatMemoryProfileUpdateRequest = ChatMemoryProfile;

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
    'preferred_name': request.preferredName,
    'assistant_name': request.assistantName,
    'role_background': request.roleBackground,
    'current_goals': request.currentGoals,
    preferences: request.preferences,
    'dislikes_to_avoid': request.dislikesToAvoid,
    'communication_style': request.communicationStyle,
    'recurring_tools_projects': request.recurringToolsProjects,
    'extra_notes': request.extraNotes
});

export { decodeChatMemorySnapshot, serializeChatMemoryProfileUpdate };
export type { ChatMemoryEntry, ChatMemoryProfile, ChatMemoryProfileUpdateRequest, ChatMemorySnapshot };

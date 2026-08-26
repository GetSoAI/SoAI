/* SoAI - Frontend WebUI conversation request boundary contracts [frontend/assets/ts/core/api/contracts/webuiConversationRequestContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';

interface ConversationCreateRequest {
    id: string;
    title: string;
}

interface ConversationCloneRequest {
    id: string;
}

interface ConversationMessageWindowRequest {
    direction?: 'tail' | 'before' | 'after' | 'around';
    limit?: number;
    cursor?: { createdAtMs: number; id: number };
    anchor?: { createdAtMs: number; id: number };
}

const serializeConversationCreateRequest = (request: ConversationCreateRequest): JsonObject => ({ id: request.id, title: request.title });

const serializeConversationCloneRequest = (request: ConversationCloneRequest): JsonObject => ({ id: request.id });

const serializeConversationBatchDeleteRequest = (ids: readonly string[]): JsonObject => ({ ids: [...ids] });
const serializeConversationTitleRequest = (title: string): JsonObject => ({ title });
const serializeConversationSettingsRequest = (settings: OpaqueJsonObject): JsonObject => ({ 'model_settings': settings });
const serializeConversationColorRequest = (color: string | null): JsonObject => ({ color });
const serializeConversationFavoriteRequest = (isFavorite: boolean): JsonObject => ({ 'is_favorite': isFavorite });
const serializeConversationArchivedRequest = (isArchived: boolean): JsonObject => ({ 'is_archived': isArchived });

const serializeConversationMessageWindowRequest = (request: ConversationMessageWindowRequest): ApiQueryParameters => {
    const direction = request.direction ?? 'tail';
    const query: ApiQueryParameters = { direction, limit: request.limit ?? 25 };
    if ((direction === 'before' || direction === 'after') && request.cursor) {
        query['cursor_created_at_ms'] = request.cursor.createdAtMs;
        query['cursor_id'] = request.cursor.id;
    }
    if (direction === 'around' && request.anchor) {
        query['anchor_created_at_ms'] = request.anchor.createdAtMs;
        query['anchor_id'] = request.anchor.id;
    }
    return query;
};

export { serializeConversationArchivedRequest, serializeConversationBatchDeleteRequest, serializeConversationCloneRequest, serializeConversationColorRequest, serializeConversationCreateRequest, serializeConversationFavoriteRequest, serializeConversationMessageWindowRequest, serializeConversationSettingsRequest, serializeConversationTitleRequest };
export type { ConversationCloneRequest, ConversationCreateRequest, ConversationMessageWindowRequest };

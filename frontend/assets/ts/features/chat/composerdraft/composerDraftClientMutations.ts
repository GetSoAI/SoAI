/* SoAI - Chat composer draft client mutation sequencing [frontend/assets/ts/features/chat/composerdraft/composerDraftClientMutations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiQueryParameters, RequestOptions } from '@core/api/types/request.ts';
import type { ConversationDraftSaveRequest } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';

interface ComposerDraftClientMutation {
    clientId: string;
    clientSequence: number;
}

class ComposerDraftClientMutations {
    readonly #clientId = generateSecureId({ prefix: 'draft_client', separator: '_' });
    #clientSequence = 0;

    get clientId(): string {
        return this.#clientId;
    }

    next(): ComposerDraftClientMutation {
        this.#clientSequence += 1;
        return { clientId: this.#clientId, clientSequence: this.#clientSequence };
    }
}

const buildComposerDraftMutationQuery = (mutation: ComposerDraftClientMutation, baseRevision: number): ApiQueryParameters => ({
    'client_id': mutation.clientId,
    'client_sequence': mutation.clientSequence,
    'base_revision': baseRevision
});

const buildComposerDraftMutationRequestOptions = (mutation: ComposerDraftClientMutation, baseRevision: number, options: RequestOptions): RequestOptions => ({
    ...options,
    query: buildComposerDraftMutationQuery(mutation, baseRevision)
});

const buildComposerDraftMutationPayloadFields = (mutation: ComposerDraftClientMutation, baseRevision: number): Pick<ConversationDraftSaveRequest, 'clientId' | 'clientSequence' | 'baseRevision'> => ({
    clientId: mutation.clientId,
    clientSequence: mutation.clientSequence,
    baseRevision
});

export { ComposerDraftClientMutations, buildComposerDraftMutationPayloadFields, buildComposerDraftMutationRequestOptions };
export type { ComposerDraftClientMutation };

/* SoAI - Chat feature composer draft load registry [frontend/assets/ts/features/chat/composerdraft/composerDraftLoadRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { createAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ComposerDraftMemoryStore } from '@features/chat/composerdraft/composerDraftMemoryStore.ts';
import { emptyParsedComposerDraft, parseComposerDraftResponse } from '@features/chat/composerdraft/composerDraftParsing.ts';
import { ComposerDraftSaveChain } from '@features/chat/composerdraft/composerDraftSaveChain.ts';
import type { ComposerDraftApi, ParsedComposerDraft } from '@features/chat/composerdraft/composerDraftTypes.ts';

interface ComposerDraftLoadRegistryOptions {
    api: ComposerDraftApi;
    memoryDrafts: ComposerDraftMemoryStore;
    saveChain: ComposerDraftSaveChain;
    isConversationPersisted(conversationId: string): boolean;
}

class ComposerDraftLoadRegistry {
    readonly #request = new LatestRequestController();
    readonly #options: ComposerDraftLoadRegistryOptions;

    constructor(options: ComposerDraftLoadRegistryOptions) {
        this.#options = options;
    }

    async readLatest(conversationId: string | null, activationSignal?: AbortSignal): Promise<ParsedComposerDraft> {
        const result = await this.#request.runLatest(async (request) => await runWithAbortSignalScope([request.signal, activationSignal], async (signal) => await this.read(conversationId, signal)));
        if (result === null) throw createAbortError('Composer draft load superseded');
        return result;
    }

    async read(conversationId: string | null, signal?: AbortSignal): Promise<ParsedComposerDraft> {
        const options = this.#options;
        if (!conversationId) return emptyParsedComposerDraft();
        if (!options.isConversationPersisted(conversationId)) return options.memoryDrafts.read(conversationId);
        await options.saveChain.wait(conversationId);
        const response = await options.api.get(conversationId, signal === undefined ? {} : { signal });
        return parseComposerDraftResponse(conversationId, response);
    }

    clear(): void {
        this.#request.invalidate();
    }
}

export { ComposerDraftLoadRegistry };
export type { ComposerDraftLoadRegistryOptions };

/* SoAI - Chat feature composer draft load registry [frontend/assets/ts/features/chat/composerdraft/composerDraftLoadRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { createAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import type { ParsedComposerDraft } from '@features/chat/composerdraft/composerDraftTypes.ts';

class ComposerDraftLoadRegistry {
    readonly #request = new LatestRequestController();

    async load(activationSignal: AbortSignal | undefined, loader: (signal: AbortSignal) => Promise<ParsedComposerDraft>): Promise<ParsedComposerDraft> {
        const result = await this.#request.runLatest(async (request) => await runWithAbortSignalScope([request.signal, activationSignal], loader));
        if (result === null) {
            throw createAbortError('Composer draft load superseded');
        }
        return result;
    }

    clear(): void {
        this.#request.invalidate();
    }
}

export { ComposerDraftLoadRegistry };

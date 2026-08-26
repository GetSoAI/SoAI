/* SoAI - Composer draft debounce lifecycle [frontend/assets/ts/features/chat/composerdraft/ComposerDraftDebounce.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComposerDraftManagerDependencies } from '@features/chat/composerdraft/composerDraftTypes.ts';

const DRAFT_SAVE_DEBOUNCE_MS = 600;

class ComposerDraftDebounce {
    readonly #setTimer: ComposerDraftManagerDependencies['setTimer'];
    readonly #clearTimer: ComposerDraftManagerDependencies['clearTimer'];
    #timer: number | null = null;

    constructor(dependencies: Pick<ComposerDraftManagerDependencies, 'setTimer' | 'clearTimer'>) {
        this.#setTimer = dependencies.setTimer;
        this.#clearTimer = dependencies.clearTimer;
    }

    schedule(functionValue: () => void): void {
        this.clear();
        this.#timer = this.#setTimer(() => {
            this.#timer = null;
            functionValue();
        }, DRAFT_SAVE_DEBOUNCE_MS);
    }

    clear(): void {
        if (this.#timer === null) return;
        this.#clearTimer(this.#timer);
        this.#timer = null;
    }
}

export { ComposerDraftDebounce };

/* SoAI - Chat backend prompt history navigation [frontend/assets/ts/pages/chat/controllers/ChatPromptHistoryNavigationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPromptHistoryResponse } from '@core/api/contracts/chatPromptHistoryContract.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { isAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatUiTaskScopeContract } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';

interface ChatPromptHistoryNavigationControllerDependencies {
    api: { get(options?: RequestOptions): Promise<ChatPromptHistoryResponse> };
    taskScope: ChatUiTaskScopeContract;
    getInput(): HTMLTextAreaElement | null;
    getLifecycleSignal(): AbortSignal | null;
    applyValue(input: HTMLTextAreaElement, value: string): void;
    reportFailure(error: Error, title: string): void;
}

class ChatPromptHistoryNavigationController {
    readonly #dependencies: ChatPromptHistoryNavigationControllerDependencies;
    readonly #editSequence = new SequenceToken();
    readonly #request = new LatestRequestController();
    #snapshot: string[] | null = null;
    #index: number | null = null;
    #draft = '';
    #initialInput: HTMLTextAreaElement | null = null;
    #initialValue = '';
    #applying = false;

    constructor(dependencies: ChatPromptHistoryNavigationControllerDependencies) {
        this.#dependencies = dependencies;
    }

    schedule(input: HTMLTextAreaElement, direction: 'up' | 'down'): void {
        if (this.#snapshot === null && this.#initialInput === null) {
            if (direction === 'down') return;
            this.#draft = input.value;
            this.#initialInput = input;
            this.#initialValue = input.value;
        }
        const token = this.#editSequence.value;
        this.#dependencies.taskScope.run('chat:promptHistoryNavigation', async () => {
            await this.#navigate(input, direction, token);
        });
    }

    noteExternalEdit(): void {
        if (this.#applying) return;
        this.invalidate();
    }

    invalidate(): void {
        this.#editSequence.invalidate();
        this.#request.invalidate();
        this.#resetSession();
    }

    async #navigate(input: HTMLTextAreaElement, direction: 'up' | 'down', token: number): Promise<void> {
        if (!this.#editSequence.isActive(token)) return;
        if (this.#snapshot === null) {
            const loaded = await this.#load(token);
            if (!loaded) return;
        }
        if (!this.#editSequence.isActive(token) || this.#dependencies.getInput() !== input) return;
        const snapshot = this.#snapshot;
        if (snapshot === null || snapshot.length === 0) {
            this.invalidate();
            return;
        }
        if (direction === 'up') {
            const nextIndex = this.#index === null ? 0 : Math.min(this.#index + 1, snapshot.length - 1);
            if (nextIndex === this.#index) return;
            this.#index = nextIndex;
            this.#apply(input, snapshot[nextIndex] ?? '');
            return;
        }
        if (this.#index === null) return;
        if (this.#index === 0) {
            const draft = this.#draft;
            this.#resetSession();
            this.#apply(input, draft);
            return;
        }
        this.#index -= 1;
        this.#apply(input, snapshot[this.#index] ?? '');
    }

    async #load(token: number): Promise<boolean> {
        let loadSucceeded = false;
        try {
            const response = await this.#request.runLatest(async (request) => {
                return await runWithAbortSignalScope([request.signal, this.#dependencies.getLifecycleSignal()], async (signal) => await this.#dependencies.api.get({ signal }));
            });
            if (response === null || !this.#editSequence.isActive(token)) return false;
            const initialInput = this.#initialInput;
            if (initialInput === null || this.#dependencies.getInput() !== initialInput || initialInput.value !== this.#initialValue) {
                this.invalidate();
                return false;
            }
            this.#snapshot = [...response.prompts];
            loadSucceeded = true;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isAbortError(runtimeError)) {
                this.invalidate();
                this.#dependencies.reportFailure(runtimeError, i18n.t('chat.promptHistory.loadFailed'));
            }
        }
        return loadSucceeded;
    }

    #apply(input: HTMLTextAreaElement, value: string): void {
        this.#applying = true;
        try {
            this.#dependencies.applyValue(input, value);
        } finally {
            this.#applying = false;
        }
    }

    #resetSession(): void {
        this.#snapshot = null;
        this.#index = null;
        this.#draft = '';
        this.#initialInput = null;
        this.#initialValue = '';
    }
}

export { ChatPromptHistoryNavigationController };

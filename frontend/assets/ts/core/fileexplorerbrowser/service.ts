/* SoAI - Shared file explorer browser service [frontend/assets/ts/core/fileexplorerbrowser/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserEntry, FileBrowserErrorResolver, FileBrowserState, ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';

import { ensureError } from '@core/errors/coerce.ts';

interface DirectoryBrowserControllerOptions {
    api: ReadOnlyFileBrowserApi;
    entryFilter?: (entry: FileBrowserEntry) => boolean;
    errorResolver: FileBrowserErrorResolver;
    onError?: (error: Error) => void;
    onStateChange: (state: FileBrowserState) => void;
}

class DirectoryBrowserController {
    readonly #api: ReadOnlyFileBrowserApi;
    readonly #entryFilter: (entry: FileBrowserEntry) => boolean;
    readonly #errorResolver: FileBrowserErrorResolver;
    readonly #onError: ((error: Error) => void) | null;
    readonly #onStateChange: (state: FileBrowserState) => void;
    #state: FileBrowserState = {
        currentPath: '/',
        workspacePathResolved: null,
        query: '',
        entries: [],
        truncated: false,
        isLoading: false,
        errorMessage: null
    };
    #sequence = 0;
    #abort: AbortController | null = null;

    constructor(options: DirectoryBrowserControllerOptions) {
        this.#api = options.api;
        this.#entryFilter = options.entryFilter ?? (() => true);
        this.#errorResolver = options.errorResolver;
        this.#onError = options.onError ?? null;
        this.#onStateChange = options.onStateChange;
    }

    destroy(): void {
        this.#abort?.abort();
        this.#abort = null;
    }

    getState(): FileBrowserState {
        return this.#state;
    }

    async initialize(path: string = '/'): Promise<void> {
        await this.navigate(path);
    }

    async refresh(): Promise<void> {
        await this.#load(this.#state.currentPath, this.#state.query);
    }

    async navigate(path: string): Promise<void> {
        await this.#load(toVirtualPath(path), '');
    }

    async search(query: string): Promise<void> {
        const normalizedQuery = query.trim();
        if (normalizedQuery === this.#state.query) {
            return;
        }
        await this.#load(this.#state.currentPath, normalizedQuery);
    }

    async clearSearch(): Promise<void> {
        if (!this.#state.query) {
            return;
        }
        await this.#load(this.#state.currentPath, '');
    }

    async #load(currentPath: string, query: string): Promise<void> {
        this.#abort?.abort();
        const abortController = new AbortController();
        const sequence = ++this.#sequence;
        this.#abort = abortController;
        this.#updateState({
            currentPath,
            query: query.trim(),
            isLoading: true,
            errorMessage: null
        });
        try {
            const payload = query.trim()
                ? await this.#api.search({
                      path: currentPath,
                      query: query.trim(),
                      limit: 400,
                      includeTotal: false,
                      signal: abortController.signal
                  })
                : await this.#api.list({ path: currentPath, limit: 400, signal: abortController.signal });
            if (abortController.signal.aborted || sequence !== this.#sequence) {
                return;
            }
            if (!isJsonValue(payload)) {
                throw new Error('File browser response must be JSON-compatible');
            }
            const parsed = parseFileBrowserLoadResponse(payload, query);
            this.#updateState({
                currentPath: parsed.currentPath,
                workspacePathResolved: parsed.workspacePathResolved,
                query: parsed.query,
                entries: parsed.entries.filter(this.#entryFilter),
                truncated: parsed.truncated,
                isLoading: false,
                errorMessage: null
            });
        } catch (error) {
            if (abortController.signal.aborted || sequence !== this.#sequence) {
                return;
            }
            const resolvedError = ensureError(error);
            this.#updateState({
                currentPath,
                query: query.trim(),
                entries: [],
                truncated: false,
                isLoading: false,
                errorMessage: this.#errorResolver.resolve(resolvedError)
            });
            this.#onError?.(resolvedError);
        }
    }

    #updateState(patch: Partial<FileBrowserState>): void {
        this.#state = { ...this.#state, ...patch };
        this.#onStateChange(this.#state);
    }
}

export { DirectoryBrowserController };

/* SoAI - Chat feature tool icon service [frontend/assets/ts/features/chat/ChatToolIconService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { ChatToolIconServiceContract } from '@core/chat/protocols.ts';

class ChatToolIconService implements ChatToolIconServiceContract {
    readonly #apiClient: ApiClient | null | undefined;
    readonly #iconCache: Map<string, string> = new Map();
    #fetchPromise: Promise<void> | null = null;
    #loaded: boolean = false;

    constructor(apiClient: ApiClient | null | undefined) {
        this.#apiClient = apiClient;
    }

    async ensureLoaded(): Promise<void> {
        if (this.#loaded) {
            return;
        }
        if (this.#fetchPromise) {
            return this.#fetchPromise;
        }
        this.#fetchPromise = this.#fetchToolIcons();
        await this.#fetchPromise;
    }

    async #fetchToolIcons(): Promise<void> {
        try {
            if (!this.#apiClient) {
                throw new Error('ChatToolIconService requires core.apiClient.webui.mcp.toolIcons()');
            }
            const response = await this.#apiClient.webui.mcp.toolIcons();
            for (const icon of response.icons) {
                this.#iconCache.set(icon.toolName, icon.src);
            }
            this.#loaded = true;
        } finally {
            this.#fetchPromise = null;
        }
    }

    getToolIcon(toolName: string): string | null {
        const icon = this.#iconCache.get(toolName);
        return icon !== undefined ? icon : null;
    }
}
export { ChatToolIconService };

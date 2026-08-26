/* SoAI - Chat page token counter usage rate tracker [frontend/assets/ts/pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';

class TokenCounterUsageRateTracker {
    #lastTokenUsage: TokenUsageSnapshot | null = null;
    #activeStreamRevision: number | null = null;
    #streamActive = false;

    clearUsage(): void {
        this.#lastTokenUsage = null;
    }

    resetStreamTracking(): void {
        this.#activeStreamRevision = null;
        this.#streamActive = false;
    }

    beginActiveStream(): void {
        this.#streamActive = true;
        this.#activeStreamRevision = null;
    }

    setPromptUsageSnapshot(usage: TokenUsageSnapshot): boolean {
        if (this.#streamActive || this.#activeStreamRevision !== null) {
            return false;
        }
        this.#lastTokenUsage = usage;
        return true;
    }

    applyStreamUsageSnapshot(usage: TokenUsageSnapshot): boolean {
        if (!this.#streamActive || usage.previewRevision === null) {
            return false;
        }
        if (this.#activeStreamRevision !== null && usage.previewRevision <= this.#activeStreamRevision) {
            return false;
        }
        this.#activeStreamRevision = usage.previewRevision;
        this.#lastTokenUsage = usage;
        return true;
    }

    completeActiveStream(): void {
        this.#activeStreamRevision = null;
        this.#streamActive = false;
    }

    getLastTokenUsage(): TokenUsageSnapshot | null {
        return this.#lastTokenUsage;
    }

    resolveTokensPerSecond(): number | null {
        if (this.#lastTokenUsage === null) {
            return 0;
        }
        if (!this.#streamActive) {
            return 0;
        }
        return this.#lastTokenUsage.completionRateTokensPerSecond;
    }
}

export { TokenCounterUsageRateTracker };

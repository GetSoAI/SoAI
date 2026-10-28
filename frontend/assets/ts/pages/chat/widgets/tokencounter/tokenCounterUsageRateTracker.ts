/* SoAI - Chat page token counter usage rate tracker [frontend/assets/ts/pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';

class TokenCounterUsageRateTracker {
    #lastTokenUsage: TokenUsageSnapshot | null = null;
    #steeringPreview: TokenUsageSnapshot | null = null;
    #activeStreamRevision: number | null = null;
    #streamActive = false;

    get isStreamActive(): boolean {
        return this.#streamActive;
    }

    clearUsage(): void {
        this.clearSteeringPreview();
        this.#lastTokenUsage = null;
    }

    clearSteeringPreview(): void {
        this.#steeringPreview = null;
    }

    getSteeringPreview(): TokenUsageSnapshot | null {
        return this.#steeringPreview;
    }

    setSteeringPreview(usage: TokenUsageSnapshot): boolean {
        if (!this.#streamActive) return false;
        this.#steeringPreview = usage;
        return true;
    }

    resetStreamTracking(): void {
        this.clearSteeringPreview();
        this.#activeStreamRevision = null;
        this.#streamActive = false;
    }

    beginActiveStream(): void {
        this.clearSteeringPreview();
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
        this.clearSteeringPreview();
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
        if (!this.#streamActive || this.#activeStreamRevision === null) {
            return 0;
        }
        return this.#lastTokenUsage.completionRateTokensPerSecond;
    }
}

export { TokenCounterUsageRateTracker };

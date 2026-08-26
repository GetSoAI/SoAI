/* SoAI - Chat stream service lifecycle state [frontend/assets/ts/features/chat/chatstreamservice/serviceLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ChatStreamServiceLifecycle {
    #active = false;
    #generation = 0;

    initialize(): boolean {
        if (this.#active) {
            return false;
        }
        this.#active = true;
        this.#generation += 1;
        return true;
    }

    dispose(): boolean {
        if (!this.#active) {
            return false;
        }
        this.#active = false;
        this.#generation += 1;
        return true;
    }

    generation(): number {
        return this.#generation;
    }

    isActive(): boolean {
        return this.#active;
    }

    isGenerationActive(generation: number): boolean {
        return this.#active && this.#generation === generation;
    }

    requireActive(operation: string): void {
        if (!this.#active) {
            throw new Error(`Chat stream service cannot ${operation} outside an active authenticated session.`);
        }
    }
}

export { ChatStreamServiceLifecycle };

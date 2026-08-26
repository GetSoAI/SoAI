/* SoAI - Chat RAG ingestion upload lifecycle manager [frontend/assets/ts/features/chat/ragingestion/ragIngestionUploadLifecycleManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class RagIngestionUploadLifecycleManager {
    #generation = 0;
    #controllers: Set<AbortController> = new Set();

    get generation(): number {
        return this.#generation;
    }

    startGeneration(): void {
        this.abortActive();
        this.#generation += 1;
    }

    createController(): AbortController {
        const controller = new AbortController();
        this.#controllers.add(controller);
        return controller;
    }

    releaseController(controller: AbortController): void {
        this.#controllers.delete(controller);
    }

    abortActive(): void {
        for (const controller of this.#controllers) {
            controller.abort();
        }
        this.#controllers.clear();
    }

    isCurrent(generation: number): boolean {
        return generation === this.#generation;
    }
}

export { RagIngestionUploadLifecycleManager };

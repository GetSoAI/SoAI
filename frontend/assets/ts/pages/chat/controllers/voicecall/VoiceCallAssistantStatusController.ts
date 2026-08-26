/* SoAI - Voice call assistant status reconciliation [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAssistantStatusController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { VoiceCallTurnManager } from '@pages/chat/controllers/voicecall/VoiceCallTurnManager.ts';
import type { VoiceCallUiStateController } from '@pages/chat/controllers/voicecall/VoiceCallUiStateController.ts';

interface VoiceCallAssistantStatusControllerDependencies {
    turnManager: VoiceCallTurnManager;
    uiState: VoiceCallUiStateController;
    isActive(): boolean;
    isPaused(): boolean;
}

class VoiceCallAssistantStatusController {
    readonly #turnManager: VoiceCallTurnManager;
    readonly #uiState: VoiceCallUiStateController;
    readonly #isActive: () => boolean;
    readonly #isPaused: () => boolean;

    constructor(dependencies: VoiceCallAssistantStatusControllerDependencies) {
        this.#turnManager = dependencies.turnManager;
        this.#uiState = dependencies.uiState;
        this.#isActive = dependencies.isActive;
        this.#isPaused = dependencies.isPaused;
    }

    handleSpeechStateChange(speaking: boolean): void {
        if (this.#isPaused()) {
            return;
        }
        if (speaking) {
            this.#uiState.setStatus('assistantSpeaking', null);
            return;
        }
        this.reconcile();
    }

    reconcile(): void {
        if (!this.#isActive() || this.#isPaused() || this.#uiState.isErrorStatus()) {
            return;
        }
        if (this.#turnManager.reconcileAssistantResponseStatus()) {
            return;
        }
        if (this.#uiState.isAssistantResponseStatus()) {
            this.#uiState.setStatus('assistantThinking', null);
        }
    }

    handlePlaybackError(): void {
        if (!this.#isActive() || this.#isPaused()) {
            return;
        }
        this.reconcile();
    }
}

export { VoiceCallAssistantStatusController };

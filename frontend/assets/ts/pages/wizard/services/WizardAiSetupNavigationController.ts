/* SoAI - Wizard AI setup step transitions and exits [frontend/assets/ts/pages/wizard/services/WizardAiSetupNavigationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AiSetupWizardStepId, WizardState } from '@features/wizard/public.ts';
import type { AiSetupFlowController } from '@pages/wizard/services/aisetup/AiSetupFlowController.ts';
import type { WizardCompletionDestination } from '@pages/wizard/services/contracts.ts';

interface WizardAiSetupNavigationControllerHost {
    state: WizardState;
    flow: AiSetupFlowController;
    showStep(index: number, options: { showNextLoading: boolean; focusHeading: boolean }): Promise<void>;
    completeWizard(destination: WizardCompletionDestination): Promise<void>;
    navigate(destination: WizardCompletionDestination): Promise<void>;
    syncNavigation(): void;
}

class WizardAiSetupNavigationController {
    readonly #host: WizardAiSetupNavigationControllerHost;

    constructor(host: WizardAiSetupNavigationControllerHost) {
        this.#host = host;
    }

    async next(stepId: AiSetupWizardStepId): Promise<void> {
        await this.#runTransition(() => this.#next(stepId));
    }

    async #next(stepId: AiSetupWizardStepId): Promise<void> {
        const flow = this.#host.flow;
        if (!flow.canContinue(stepId)) {
            this.#host.syncNavigation();
            return;
        }
        if (stepId === 'ai_progress') {
            await this.#startChatting();
            return;
        }
        flow.continueFrom(stepId);
        await this.#host.showStep(this.#host.state.steps.indexOf(stepId) + 1, { showNextLoading: true, focusHeading: true });
    }

    async completeFromSummary(): Promise<void> {
        await this.#runTransition(() => this.#completeFromSummary());
    }

    async #completeFromSummary(): Promise<void> {
        if (this.#host.flow.hasReadyModel()) {
            await this.#startChatting();
            return;
        }
        if (this.#host.state.isAiSetupResume) {
            await this.#host.navigate('default');
            return;
        }
        await this.#host.completeWizard('default');
    }

    async #startChatting(): Promise<void> {
        if (this.#host.flow.prepareHandoff() === null) return;
        if (this.#host.state.isAiSetupResume) {
            await this.#host.navigate('chat');
            return;
        }
        await this.#host.completeWizard('chat');
    }

    async finishLater(): Promise<void> {
        await this.#runTransition(async () => {
            this.#host.flow.leave('finished_later');
            await this.#showCompletion();
        });
    }

    async skip(): Promise<void> {
        await this.#runTransition(async () => {
            this.#host.flow.leave('skipped');
            await this.#showCompletion();
        });
    }

    async showStep(stepId: AiSetupWizardStepId): Promise<void> {
        await this.#runTransition(async () => {
            const index = this.#host.state.steps.indexOf(stepId);
            if (index >= 0) await this.#host.showStep(index, { showNextLoading: false, focusHeading: true });
        });
    }

    async #showCompletion(): Promise<void> {
        await this.#host.showStep(this.#host.state.steps.indexOf('complete'), { showNextLoading: false, focusHeading: true });
    }

    async #runTransition(operation: () => Promise<void>): Promise<void> {
        if (this.#host.state.isBusy) return;
        this.#host.state.isBusy = true;
        this.#host.syncNavigation();
        try {
            await operation();
        } finally {
            this.#host.state.isBusy = false;
            this.#host.syncNavigation();
        }
    }
}

export { WizardAiSetupNavigationController };
export type { WizardAiSetupNavigationControllerHost };

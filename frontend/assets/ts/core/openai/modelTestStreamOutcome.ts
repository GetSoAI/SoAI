/* SoAI - Shared OpenAI model test stream outcomes [frontend/assets/ts/core/openai/modelTestStreamOutcome.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ModelTestStreamResult = 'passed' | 'empty';

type ModelTestStreamFailureOutcome = 'load_error' | 'timeout' | 'disconnected' | 'cancelled';

class ModelTestStreamError extends Error {
    readonly outcome: ModelTestStreamFailureOutcome;

    constructor(message: string, outcome: ModelTestStreamFailureOutcome) {
        super(message);
        this.name = 'ModelTestStreamError';
        this.outcome = outcome;
    }
}

const readModelTestStreamFailureOutcome = (error: Error): ModelTestStreamFailureOutcome => (error instanceof ModelTestStreamError ? error.outcome : 'load_error');

const readModelTestStreamResult = (visibleText: string): ModelTestStreamResult => (visibleText.trim() ? 'passed' : 'empty');

export { ModelTestStreamError, readModelTestStreamFailureOutcome, readModelTestStreamResult };
export type { ModelTestStreamFailureOutcome, ModelTestStreamResult };

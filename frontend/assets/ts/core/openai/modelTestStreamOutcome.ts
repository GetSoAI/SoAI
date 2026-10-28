/* SoAI - Shared OpenAI model test stream outcomes [frontend/assets/ts/core/openai/modelTestStreamOutcome.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ModelTestFailureMetadata {
    code: string | null;
    runId: string | null;
}

const normalizeModelTestFailureMetadata = (code: JsonValue | undefined, runId: JsonValue | undefined): ModelTestFailureMetadata | null => {
    const safeCode = isString(code) && /^[a-z][a-z0-9_]{0,127}$/.test(code) ? code : null;
    const safeRunId = isString(runId) && /^[a-zA-Z0-9_-]{1,160}$/.test(runId) ? runId : null;
    return safeCode === null && safeRunId === null ? null : { code: safeCode, runId: safeRunId };
};

type ModelTestStreamResult = 'passed' | 'empty';

type ModelTestStreamFailureOutcome = 'load_error' | 'timeout' | 'disconnected' | 'cancelled';

class ModelTestStreamError extends Error {
    readonly outcome: ModelTestStreamFailureOutcome;

    readonly failure: ModelTestFailureMetadata | null;

    constructor(message: string, outcome: ModelTestStreamFailureOutcome, failure: ModelTestFailureMetadata | null = null) {
        super(message);
        this.name = 'ModelTestStreamError';
        this.outcome = outcome;
        this.failure = normalizeModelTestFailureMetadata(failure?.code, failure?.runId);
    }
}

const readModelTestStreamFailureOutcome = (error: Error): ModelTestStreamFailureOutcome => (error instanceof ModelTestStreamError ? error.outcome : 'load_error');

const readModelTestStreamResult = (visibleText: string): ModelTestStreamResult => (visibleText.trim() ? 'passed' : 'empty');

export { normalizeModelTestFailureMetadata, ModelTestStreamError, readModelTestStreamFailureOutcome, readModelTestStreamResult };
export type { ModelTestFailureMetadata, ModelTestStreamFailureOutcome, ModelTestStreamResult };

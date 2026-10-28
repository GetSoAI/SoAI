/* SoAI - Frontend initialization stage failure context [frontend/assets/ts/app/bootstrap/stages/initializationStage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isString } from '@core/typeGuards.ts';

type InitializationStage = 'entrypoint' | 'criticalServices' | 'authentication' | 'session' | 'routeRendering' | 'background';

interface InitializationFailure {
    stage: InitializationStage | null;
    reference: string;
}

const CLIENT_REFERENCE_LENGTH = 12;
const failureStages = new WeakMap<Error, InitializationStage>();
const failureReferences = new WeakMap<Error, string>();

const runInitializationStage = async <T>(stage: InitializationStage, operation: () => T | Promise<T>): Promise<T> => {
    try {
        return await operation();
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!failureStages.has(runtimeError)) failureStages.set(runtimeError, stage);
        throw runtimeError;
    }
};

const describeInitializationFailure = (error: Error): InitializationFailure => {
    let reference = failureReferences.get(error);
    if (reference === undefined) {
        const traceId = error instanceof APIError ? error.traceId : undefined;
        reference = isString(traceId) && traceId.trim() ? traceId.trim() : generateSecureId({ format: 'hex' }).slice(0, CLIENT_REFERENCE_LENGTH);
        failureReferences.set(error, reference);
    }
    return { stage: failureStages.get(error) ?? null, reference };
};

const reportInitializationFailure = (module: string, message: string, failure: Error, reported: Error = failure): void => {
    const { stage, reference } = describeInitializationFailure(failure);
    errorHandler.error(module, message, reported, { stage: stage ?? 'unknown', context: { reference } });
};

const isIntentionalInitializationCancellation = <T>(error: T): boolean => isAbortError(error) || isLifecycleCancellationError(error);

export { describeInitializationFailure, isIntentionalInitializationCancellation, reportInitializationFailure, runInitializationStage };
export type { InitializationFailure, InitializationStage };

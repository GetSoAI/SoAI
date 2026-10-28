/* SoAI - Interface emphasis font readiness before first presentation [frontend/assets/ts/core/layout/typographyReadiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';

const prepareInterfaceEmphasisFont = async (documentRef: Document, signal: AbortSignal): Promise<void> => {
    await withAbortableTimeout(
        (timeoutSignal) =>
            runWithAbortSignalScope([signal, timeoutSignal], (scopeSignal) => {
                throwIfAborted(scopeSignal);
                return raceWithAbortSignal(documentRef.fonts.load('italic 400 15px SoAIType'), scopeSignal);
            }),
        { timeoutMs: 1500, timeoutMessage: 'Interface emphasis font did not become ready.' }
    );
};

export { prepareInterfaceEmphasisFont };

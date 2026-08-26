/* SoAI - Shared lifecycle abort signals [frontend/assets/ts/core/lifecycle/abortSignals.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const signalAborted = (signal: AbortSignal | null | undefined): boolean => Boolean(signal && signal.aborted);

const runAbortable = async (signal: AbortSignal | null | undefined, operation: () => Promise<void>): Promise<boolean> => {
    if (signalAborted(signal)) {
        return false;
    }
    try {
        await operation();
    } catch (error) {
        if (signalAborted(signal)) {
            return false;
        }
        throw error;
    }
    return !signalAborted(signal);
};

export { runAbortable, signalAborted };

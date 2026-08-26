/* SoAI - Shared primitives with abortable timeout [frontend/assets/ts/core/primitives/withAbortableTimeout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface WithAbortableTimeoutOptions {
    timeoutMs: number;
    timeoutMessage: string;
}

const withAbortableTimeout = async <T>(operation: (signal: AbortSignal) => Promise<T>, options: WithAbortableTimeoutOptions): Promise<T> => {
    const timeoutMs = options.timeoutMs;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new Error('withAbortableTimeout requires a positive finite timeoutMs value');
    }
    const timeoutMessage = options.timeoutMessage.trim();
    if (!timeoutMessage) {
        throw new Error('withAbortableTimeout requires a non-empty timeoutMessage');
    }

    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const timeoutPromise = new Promise<never>((_unusedValue, reject) => {
        timeoutId = setTimeout(() => {
            controller.abort();
            reject(new Error(timeoutMessage));
        }, timeoutMs);
    });

    try {
        return await Promise.race([operation(controller.signal), timeoutPromise]);
    } finally {
        if (timeoutId !== null) {
            clearTimeout(timeoutId);
        }
    }
};

export { withAbortableTimeout };
export type { WithAbortableTimeoutOptions };

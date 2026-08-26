/* SoAI - Promise timeout primitive [frontend/assets/ts/core/primitives/withTimeout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type WithTimeoutOptions = {
    timeoutMs: number;
    timeoutMessage: string;
};

const withTimeout = async <T>(promise: Promise<T>, options: WithTimeoutOptions): Promise<T> => {
    const timeoutMs = options.timeoutMs;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new Error('withTimeout requires a positive finite timeoutMs value');
    }
    const timeoutMessage = options.timeoutMessage.trim();
    if (!timeoutMessage) {
        throw new Error('withTimeout requires a non-empty timeoutMessage');
    }

    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const timeoutPromise = new Promise<never>((_unusedValue, reject) => {
        timeoutId = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
    });

    try {
        return await Promise.race([promise, timeoutPromise]);
    } finally {
        if (timeoutId !== null) {
            clearTimeout(timeoutId);
        }
    }
};

export { withTimeout };
export type { WithTimeoutOptions };

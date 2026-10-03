/* SoAI - Log subscription failure classification [frontend/assets/ts/core/realtime/streammanager/transport/logStreamError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class LogStreamError extends Error {
    readonly recovery: 'retry' | 'stop' | 'await-connection';
    readonly traceId: string | null;

    constructor(message: string, recovery: 'retry' | 'stop' | 'await-connection', traceId: string | null = null) {
        super(message);
        this.name = 'LogStreamError';
        this.recovery = recovery;
        this.traceId = traceId;
    }
}

export { LogStreamError };

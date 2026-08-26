/* SoAI - Shared runtime environment kernel [frontend/assets/ts/core/runtimeenv/kernel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createModuleLogger, type ModuleLogger } from '@core/moduleContext.ts';
import { ensureError } from '@core/errors/coerce.ts';

const kernelLog: ModuleLogger = createModuleLogger('Kernel', { defaultLevel: 'error' });

class Kernel {
    initialized: boolean;
    bootPromise: Promise<boolean> | null;

    constructor() {
        this.initialized = false;
        this.bootPromise = null;
    }

    start(): Promise<boolean> {
        return this.bootPromise ?? (this.bootPromise = this.initialize());
    }

    async initialize(): Promise<boolean> {
        if (this.initialized) return true;
        try {
            this.initialized = true;
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            kernelLog('error', 'Initialization failed', runtimeError);
            throw runtimeError;
        }
    }

    refresh(): Promise<boolean> {
        this.initialized = false;
        return this.start();
    }
}

let kernelInstance: Kernel | null = null;

const getKernel = (): Kernel => {
    if (!kernelInstance) {
        kernelInstance = new Kernel();
    }
    return kernelInstance;
};

const resetKernel = (): void => {
    kernelInstance = null;
};

export { Kernel, getKernel, resetKernel };

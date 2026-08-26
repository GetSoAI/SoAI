/* SoAI - Updates page system check request controller [frontend/assets/ts/pages/updates/controllers/updatesSystemCheckRequestController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';

interface UpdatesSystemCheckRequestDependencies {
    readonly checkUpdates: () => Promise<SoftwareUpdateCheckResponse>;
    readonly wait: (ms: number) => Promise<void>;
    readonly maxAttempts: number;
    readonly retryDelayMs: number;
}

interface UpdatesSystemCheckRequestResult {
    readonly payload: SoftwareUpdateCheckResponse | null;
    readonly error: Error | null;
}

const requestUpdatesSystemPayload = async (dependencies: UpdatesSystemCheckRequestDependencies): Promise<UpdatesSystemCheckRequestResult> => {
    let lastError: Error | null = null;
    for (let attempt = 0; attempt < dependencies.maxAttempts; attempt += 1) {
        try {
            return { payload: await dependencies.checkUpdates(), error: null };
        } catch (error) {
            lastError = ensureError(error);
            if (attempt < dependencies.maxAttempts - 1) {
                await dependencies.wait(dependencies.retryDelayMs * (attempt + 1));
            }
        }
    }
    return { payload: null, error: lastError };
};

export { requestUpdatesSystemPayload };

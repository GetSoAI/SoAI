/* SoAI - Shared frontend storage runtime [frontend/assets/ts/core/storage/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageService } from '@core/storage/StorageService.ts';
import { isStorageServiceContract } from '@core/storage/guards.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

const STORAGE_SERVICE_ID = 'core.storage';

const requireStorageService = (): StorageService => {
    const candidate = resolveKernelService(STORAGE_SERVICE_ID);
    if (!isStorageServiceContract(candidate)) {
        throw new Error('Storage service is not configured');
    }
    return candidate;
};

const getStorageService = (): StorageService | null => {
    const candidate = resolveOptionalKernelService(STORAGE_SERVICE_ID);
    return isStorageServiceContract(candidate) ? candidate : null;
};

export { getStorageService, requireStorageService, STORAGE_SERVICE_ID };

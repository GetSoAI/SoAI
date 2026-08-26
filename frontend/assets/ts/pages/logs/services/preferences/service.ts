/* SoAI - Logs page preferences service [frontend/assets/ts/pages/logs/services/preferences/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLogValidation, VALID_LOG_LINE_LIMITS } from '@core/logvalidation/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { DEFAULT_LOG_LINE_LIMIT } from '@pages/logs/contracts/constants.ts';
import { resolveLogLineOptionsFromStorage } from '@pages/logs/services/service.ts';

const resolveLogLineLimitFromStorage = (storage: StorageService | null | undefined): number => {
    if (!storage || !isObject(storage)) {
        return DEFAULT_LOG_LINE_LIMIT;
    }
    const getLogLineLimit = storage['getLogLineLimit'];
    if (!isFunction(getLogLineLimit)) {
        return DEFAULT_LOG_LINE_LIMIT;
    }
    const lineLimit = getLogLineLimit(DEFAULT_LOG_LINE_LIMIT);
    const limitResult = getLogValidation().validateLogLineLimit(lineLimit);
    return limitResult.valid && limitResult.limit !== null ? limitResult.limit : DEFAULT_LOG_LINE_LIMIT;
};

const resolveLogLineOptions = (storage: StorageService | null | undefined): readonly number[] => {
    const fromStorage = resolveLogLineOptionsFromStorage(storage);
    if (fromStorage) {
        const allowed = new Set(VALID_LOG_LINE_LIMITS);
        const filtered = fromStorage.filter((value) => allowed.has(value));
        return filtered.length ? filtered : VALID_LOG_LINE_LIMITS;
    }
    return VALID_LOG_LINE_LIMITS;
};

export { resolveLogLineLimitFromStorage, resolveLogLineOptions };

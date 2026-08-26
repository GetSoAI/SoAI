/* SoAI - Shared license service actions [frontend/assets/ts/core/licenseservice/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiClient } from '@core/api/service.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { isInitializableLanguageService } from '@core/licenseservice/guards.ts';
import type { LicenseData } from '@core/licenseservice/types.ts';

const ensureTranslationsReady = async (): Promise<void> => {
    const candidate = getLanguageService();
    if (!isInitializableLanguageService(candidate)) {
        return;
    }
    const initializeResult = candidate.initialize();
    if (isObject(initializeResult) && isFunction(initializeResult['then'])) {
        await initializeResult;
    }
};

const fetchLicenseData = async (): Promise<LicenseData> => {
    const payload = await getApiClient().system.license();
    return { licenseText: payload.licenseText };
};

const fetchRequirementsText = async (): Promise<string | null> => {
    const payload = await getApiClient().system.requirements();
    const text = payload.trim();
    return text ? payload : null;
};

export { ensureTranslationsReady, fetchLicenseData, fetchRequirementsText };

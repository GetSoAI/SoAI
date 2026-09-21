/* SoAI - Shared language service state [frontend/assets/ts/core/languageservice/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { log } from '@core/languageservice/constants.ts';
import type { LanguageServiceRuntime } from '@core/languageservice/internalContracts.ts';
import type { StorageInterface } from '@core/languageservice/types.ts';

const resolveInitialLanguagePreference = (service: LanguageServiceRuntime, store: StorageInterface | null): string => {
    const stored = store?.getLanguage?.();
    if (stored) {
        if (service.languages.has(stored)) {
            return stored;
        }
        log('warn', `Ignoring unsupported stored language preference: ${stored}`);
    }
    if (service.languages.has(service.defaultLanguage)) {
        return service.defaultLanguage;
    }
    throw new Error('Unable to resolve initial language preference');
};

export { resolveInitialLanguagePreference };

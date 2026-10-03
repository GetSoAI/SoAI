/* SoAI - Startup recovery messages independent of catalog requests [frontend/assets/ts/core/languageservice/bootMessages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLanguageService } from '@core/languageservice/service.ts';
import { resolveStorage } from '@core/languageservice/adapters.ts';
import { resolveInitialLanguagePreference } from '@core/languageservice/state.ts';
import type { BootMessageCatalog } from '@core/languageservice/bootMessageCatalog.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';

declare const __SOAI_BOOT_MESSAGES__: BootMessageCatalog;

const resolveBootMessages = (): { language: string; direction: string; t: (key: string, parameters?: JsonRecord) => string } => {
    const service = getLanguageService();
    const catalog = __SOAI_BOOT_MESSAGES__;
    const languages = new Map(catalog.locales.map((locale) => [locale.code, locale]));
    const language = service.initialized && languages.has(service.currentLanguage) ? service.currentLanguage : resolveInitialLanguagePreference({ languages, defaultLanguage: catalog.defaultLanguage }, resolveStorage());
    const locale = languages.get(language);
    if (!locale) throw new Error('Startup recovery locale is unavailable');
    return {
        language,
        direction: locale.direction,
        t: (key, parameters = {}): string => {
            const template = service.getTranslation(key, language) ?? locale.messages[key];
            if (template === undefined) throw new Error(`Startup recovery translation is unavailable: ${key}`);
            return service.interpolate(template, parameters, locale.direction);
        }
    };
};

export { resolveBootMessages };

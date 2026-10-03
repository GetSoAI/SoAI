/* SoAI - Language option construction and selection [frontend/assets/ts/core/languageservice/languageOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LanguageEntryWithCountryCode } from '@core/languageservice/types.ts';

interface LanguageOption {
    code: string;
    countryCode: string | null;
    name: string | null;
}

const toLanguageOption = (value: LanguageEntryWithCountryCode): LanguageOption => ({
    code: value.code,
    countryCode: value.countryCode ?? null,
    name: value.name
});

const buildLanguageOptions = (languageCandidates: ReadonlyArray<LanguageEntryWithCountryCode>, currentLanguage: string): Array<{ value: string; label: string; countryCode: string | null }> => {
    const options = languageCandidates.map((entry) => {
        const language = toLanguageOption(entry);
        return {
            value: language.code,
            label: String(language.name ?? language.code),
            countryCode: language.countryCode
        };
    });

    if (!options.some((option) => option.value === currentLanguage)) {
        options.push({ value: currentLanguage, label: currentLanguage, countryCode: null });
    }

    return options;
};

export { buildLanguageOptions };

/* SoAI - Language option construction and selection [frontend/assets/ts/core/languageservice/languageOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LanguageEntryWithFlag } from '@core/languageservice/types.ts';

interface LanguageOption {
    code: string;
    flag: string | null;
    name: string | null;
}

const toLanguageOption = (value: LanguageEntryWithFlag): LanguageOption => ({
    code: value.code,
    flag: value.flag ?? null,
    name: value.name
});

const buildLanguageOptions = (languageCandidates: ReadonlyArray<LanguageEntryWithFlag>, currentLanguage: string): Array<{ value: string; label: string }> => {
    const options = languageCandidates.map((entry) => {
        const language = toLanguageOption(entry);
        return {
            value: language.code,
            label: `${language.flag ? language.flag + ' ' : ''}${String(language.name ?? language.code)}`
        };
    });

    if (!options.some((option) => option.value === currentLanguage)) {
        options.push({ value: currentLanguage, label: currentLanguage });
    }

    return options;
};

export { buildLanguageOptions };

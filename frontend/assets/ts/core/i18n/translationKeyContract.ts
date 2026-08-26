/* SoAI - Extensible frontend edition translation key contract [frontend/assets/ts/core/i18n/translationKeyContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePluralBaseKey, BaseTranslationKey } from '@core/i18n/translationKeys.generated.ts';

interface TranslationKeyRegistry {
    base: BaseTranslationKey;
}

interface PluralBaseKeyRegistry {
    base: BasePluralBaseKey;
}

type TranslationKey = TranslationKeyRegistry[keyof TranslationKeyRegistry];
type PluralBaseKey = PluralBaseKeyRegistry[keyof PluralBaseKeyRegistry];

export type { PluralBaseKey, PluralBaseKeyRegistry, TranslationKey, TranslationKeyRegistry };

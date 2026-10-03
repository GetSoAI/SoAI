/* SoAI - Shared localization Intl formatter cache [frontend/assets/ts/core/localization/intlCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const MAX_CACHED_INTL_OBJECTS = 64;

const createIntlCache = <TOptions, TIntl>(create: (locale: string, options: TOptions) => TIntl): ((locale: string, options: TOptions) => TIntl) => {
    const cache = new Map<string, TIntl>();
    return (locale, options) => {
        const key = `${locale}\u0000${JSON.stringify(options)}`;
        const cached = cache.get(key);
        if (cached !== undefined) {
            return cached;
        }
        const created = create(locale, options);
        if (cache.size >= MAX_CACHED_INTL_OBJECTS) {
            cache.clear();
        }
        cache.set(key, created);
        return created;
    };
};

const resolveNumericPresentationLocale = (locale: string): string => {
    const requested = new Intl.Locale(locale);
    return requested.language === 'fa' && requested.numberingSystem === undefined ? new Intl.Locale(requested, { numberingSystem: 'latn' }).toString() : locale;
};

const getNumberFormat = createIntlCache((locale, options: Intl.NumberFormatOptions) => new Intl.NumberFormat(resolveNumericPresentationLocale(locale), options));
const getDateTimeFormat = createIntlCache((locale, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(resolveNumericPresentationLocale(locale), options));
const getRelativeTimeFormat = createIntlCache((locale, options: Intl.RelativeTimeFormatOptions) => new Intl.RelativeTimeFormat(resolveNumericPresentationLocale(locale), options));
const getCollator = createIntlCache((locale, options: Intl.CollatorOptions) => new Intl.Collator(locale, options));
const getListFormat = createIntlCache((locale, options: Intl.ListFormatOptions) => new Intl.ListFormat(locale, options));

export { getCollator, getDateTimeFormat, getListFormat, getNumberFormat, getRelativeTimeFormat };

/* SoAI - Automation page locale [frontend/assets/ts/pages/automation/widgets/calendar/locale.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getResolvedLocalizationLocale } from '@core/localization/public.ts';
import { isString } from '@core/typeGuards.ts';

const resolveAutomationLocalizationLocale = (): string => {
    const locale = getResolvedLocalizationLocale();
    if (!isString(locale) || !locale.trim()) {
        throw new Error('Automation localization locale could not be resolved');
    }
    return locale.trim();
};

export { resolveAutomationLocalizationLocale };

/* SoAI - Model detail page guards implementation [frontend/assets/ts/pages/modeldetail/guards/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';

type RequireConfiguredIconOptions = {
    subject: string;
    verb: 'require' | 'requires';
};

const requireConfiguredIcon = (icons: Record<string, TrustedHtml>, name: string, options: RequireConfiguredIconOptions): TrustedHtml => {
    const iconMarkup = icons[name];
    if (!iconMarkup || !iconMarkup.html.trim()) {
        throw new Error(`${options.subject} ${options.verb} icon "${name}"`);
    }
    return iconMarkup;
};

export { requireConfiguredIcon };

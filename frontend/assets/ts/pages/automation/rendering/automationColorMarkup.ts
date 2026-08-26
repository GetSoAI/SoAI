/* SoAI - Automation page color markup [frontend/assets/ts/pages/automation/rendering/automationColorMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { uiAttr } from '@core/security/uiHtml.ts';
import type { AutomationColor } from '@features/automation/public.ts';

const renderAutomationColorAttribute = (color: AutomationColor): string => {
    if (!color) {
        return '';
    }
    return ` data-automation-color="${uiAttr(color).html}"`;
};

export { renderAutomationColorAttribute };

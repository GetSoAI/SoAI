/* SoAI - Shared label attribute renderer for accessible interactive controls [frontend/assets/ts/core/security/labelAttributes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/htmlSanitizer.ts';
import { uiAttributes } from '@core/security/uiHtml.ts';

interface LabelAttributesInput {
    ariaLabel: string;
    tooltip?: string | null | undefined;
}

const renderLabelAttributes = (input: string | LabelAttributesInput): TrustedHtml => {
    const ariaLabel = typeof input === 'string' ? input : input.ariaLabel;
    const tooltip = typeof input === 'string' ? input : (input.tooltip ?? input.ariaLabel);
    return uiAttributes({ 'aria-label': ariaLabel, 'data-tooltip': tooltip });
};

export { renderLabelAttributes };
export type { LabelAttributesInput };

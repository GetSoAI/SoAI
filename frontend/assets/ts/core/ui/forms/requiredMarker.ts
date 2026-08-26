/* SoAI - Shared UI required marker [frontend/assets/ts/core/ui/forms/requiredMarker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';

const REQUIRED_FIELD_MARKER_CLASS = 'ui-required-marker';

type RequiredFieldMarkerOptions = {
    hidden?: boolean | undefined;
    id?: string | undefined;
};

const renderRequiredFieldMarker = (options: RequiredFieldMarkerOptions = {}): TrustedHtml => {
    const hiddenClass = options.hidden === true ? ' u-hidden' : '';
    const idAttribute = options.id ? uiHtml` id="${uiAttr(options.id)}"` : EMPTY_UI_HTML;
    return uiHtml`<span${idAttribute} class="${REQUIRED_FIELD_MARKER_CLASS}${hiddenClass}" aria-hidden="true">*</span>`;
};

const renderRequiredFieldLabel = (labelText: string, options: RequiredFieldMarkerOptions = {}): TrustedHtml => {
    return uiHtml`${uiText(labelText)} ${renderRequiredFieldMarker(options)}`;
};

const renderRequiredFieldLabelHtml = (labelText: string, options: RequiredFieldMarkerOptions = {}): string => {
    return renderRequiredFieldLabel(labelText, options).html;
};

export { renderRequiredFieldLabel, renderRequiredFieldLabelHtml, renderRequiredFieldMarker };

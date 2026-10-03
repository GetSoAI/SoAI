/* SoAI - Canvas text typography and surrounding reading direction [frontend/assets/ts/features/charts/rendering/textStyle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getComputedStyleStrict } from '@core/environment/public.ts';
import { isRtl } from '@core/layout/direction.ts';

const getChartTextStyle = (element: HTMLElement | null): { fontFamily: string; direction: CanvasDirection } => {
    if (element === null) throw new Error('Chart text requires its surface element');
    const fontFamily = getComputedStyleStrict(element).fontFamily.trim();
    if (!fontFamily) throw new Error('Chart text requires the inherited UI font family');
    return { fontFamily, direction: isRtl(element.parentElement ?? element) ? 'rtl' : 'ltr' };
};

export { getChartTextStyle };

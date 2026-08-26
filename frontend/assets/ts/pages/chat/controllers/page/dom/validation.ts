/* SoAI - Chat page validation [frontend/assets/ts/pages/chat/controllers/page/dom/validation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TextZoomResult } from '@core/logvalidation/types.ts';
import { isNumber, isString } from '@core/typeGuards.ts';

const validateTextZoomValue = (validateTextZoom: (zoom: number | null) => TextZoomResult, logError: (message: string, error?: Error) => void, zoom: number | null, contextMessage: string): number | null => {
    const validationResult = validateTextZoom(zoom);
    if (validationResult.valid) {
        return isNumber(validationResult.zoom) ? validationResult.zoom : null;
    }
    const errorValue = validationResult.error;
    const errorMessage = isString(errorValue) ? errorValue : 'Invalid text zoom';
    logError(`${contextMessage}: ${errorMessage}`);
    return null;
};

export { validateTextZoomValue };

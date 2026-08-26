/* SoAI - Typed parsing helpers for comparison-turn DOM attributes [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnDomParsingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedAttributeValue, parseNonNegativeIntegerFromString } from '@core/dom/attributes.ts';

const parseNonNegativeIntegerAttribute = (value: string | null, field: string): number | null => {
    const normalized = optionalTrimmedAttributeValue(value);
    if (normalized === null) {
        return null;
    }
    return parseNonNegativeIntegerFromString(normalized, `Chat comparison attribute ${field}`);
};

export { parseNonNegativeIntegerAttribute };

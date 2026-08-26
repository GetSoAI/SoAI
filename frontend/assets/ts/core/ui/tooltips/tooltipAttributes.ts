/* SoAI - Shared UI tooltip attributes [frontend/assets/ts/core/ui/tooltips/tooltipAttributes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined, isString } from '@core/typeGuards.ts';

type TooltipTextValue = string | number | boolean | null | undefined;

const normalizeTooltipText = (value: TooltipTextValue): string => {
    const raw = isNullOrUndefined(value) ? '' : String(value);
    return raw.trim();
};

export const setTooltipText = (target: HTMLElement, text: TooltipTextValue): void => {
    const normalized = normalizeTooltipText(text);
    if (normalized) {
        target.dataset['tooltip'] = normalized;
    } else {
        delete target.dataset['tooltip'];
    }
};

export const getTooltipText = (target: HTMLElement): string | null => {
    const raw = target.dataset['tooltip'] ?? null;
    if (!isString(raw)) {
        return null;
    }
    const normalized = raw.trim();
    return normalized ? normalized : null;
};

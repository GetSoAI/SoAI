/* SoAI - Translation template interpolation for worker-rendered chat markup [frontend/assets/ts/features/chat/messagerenderworker/translationInterpolation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

const interpolateTranslationTemplate = (template: string, parameters: Record<string, JsonValue | null | undefined> | null): string => {
    if (!parameters) {
        return template;
    }
    const keys = Object.keys(parameters);
    if (keys.length === 0) {
        return template;
    }
    return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in parameters ? String(parameters[key]) : match));
};

export { interpolateTranslationTemplate };

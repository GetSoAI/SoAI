/* SoAI - Model detail page rendering layer parameter count badge tone [frontend/assets/ts/pages/modeldetail/rendering/parameterCountBadgeTone.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';

const PARAMETER_COUNT_BADGE_TONE_CLASSES = ['status-green', 'status-blue', 'status-orange', 'status-red', 'status-grey'];

const normalizeCountFromLabel = (value: string): number | null => {
    const match = value.match(/\d[\d\s.,]*/);
    if (!match) {
        return null;
    }
    const normalized = match[0].replace(/[^\d]/g, '');
    if (!normalized) {
        return null;
    }
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
};

const resolveFallbackToneFromText = (value: string): string => {
    const text = value.trim().toLowerCase();
    if (!text) {
        return 'status-grey';
    }
    let hash = 0;
    for (let index = 0; index < text.length; index += 1) {
        hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
    }
    const palette = ['status-blue', 'status-green', 'status-orange', 'status-grey'];
    return palette[Math.abs(hash) % palette.length] || 'status-blue';
};

const resolveParameterCountBadgeTone = (value: number | string): string => {
    const count = typeof value === 'number' ? value : isString(value) ? normalizeCountFromLabel(value) : null;
    if (typeof count === 'number') {
        if (count <= 0) {
            return 'status-red';
        }
        if (count <= 2) {
            return 'status-orange';
        }
        if (count <= 8) {
            return 'status-blue';
        }
        return 'status-green';
    }
    return resolveFallbackToneFromText(isString(value) ? value : '');
};

export { PARAMETER_COUNT_BADGE_TONE_CLASSES, resolveParameterCountBadgeTone };

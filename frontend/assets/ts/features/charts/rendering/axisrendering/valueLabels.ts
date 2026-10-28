/* SoAI - Compact chart axis labels with tick precision preservation [frontend/assets/ts/features/charts/rendering/axisrendering/valueLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatInvariantNumber } from '@core/localization/public.ts';

const formatYAxisLabels = (values: readonly number[], formatValue: (value: number) => string, width: number): string[] => {
    const labels = values.map(formatValue);
    const numbers = labels.map((label) => {
        const match = /^([+-]?(?:\d+(?:\.\d*)?|\.\d+))([^\d]*)$/u.exec(label);
        const numeric = match?.[1] === undefined ? Number.NaN : Number(match[1]);
        return Number.isFinite(numeric) ? { numeric, suffix: match?.[2] ?? '' } : null;
    });
    for (let precision = width <= 420 ? 0 : 1; precision <= 8; precision += 1) {
        let accurate = true;
        const candidates = numbers.map((entry, index) => {
            if (entry === null) return labels[index] ?? '';
            let step = Number.POSITIVE_INFINITY;
            for (const other of numbers) {
                if (other !== null && other.suffix === entry.suffix && other.numeric !== entry.numeric) step = Math.min(step, Math.abs(other.numeric - entry.numeric));
            }
            const compact = entry.suffix === '' && width <= 420 && Math.abs(entry.numeric) >= 1000;
            const divisor = compact ? 1000 ** Math.min(4, Math.floor(Math.log10(Math.abs(entry.numeric)) / 3)) : 1;
            const rounded = Number((entry.numeric / divisor).toFixed(precision)) * divisor;
            const tolerance = Math.min(step / 10, Math.abs(entry.numeric) / 100 || step / 10);
            if (Math.abs(rounded - entry.numeric) > tolerance + Number.EPSILON * Math.max(1, Math.abs(entry.numeric))) accurate = false;
            return `${formatInvariantNumber(rounded, { maximumFractionDigits: precision, notation: compact ? 'compact' : 'standard' })}${entry.suffix}`;
        });
        if (accurate && new Set(candidates).size === new Set(labels).size) return candidates;
    }
    return labels;
};

export { formatYAxisLabels };

/* SoAI - Shared frontend speed test [frontend/assets/ts/core/speedTest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatDuration } from '@core/primitives/duration.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';

interface SpeedTestData {
    status?: string | null;
    estimatedMs?: number | null;
    bytesPerSecond?: number | null;
    mode?: string | null;
    estimationFactor?: number | null;
    sampleBytes?: number | null;
}

interface DisplayResult {
    estimateMs: number | null;
    estimateLabel: string;
    throughputLabel: string;
    mode: string;
    factor: number;
    sampleLabel: string;
}

const toFinite = (value: number | null | undefined): number | null => {
    if (value === null || value === undefined || !Number.isFinite(value) || value < 0) {
        return null;
    }
    return value;
};

const formatThroughputValue = (value: number | null | undefined): string => {
    const numeric = toFinite(value);
    if (numeric === null || numeric <= 0) {
        return '';
    }
    return `${formatBytes(numeric)}/s`;
};

const formatSampleValue = (value: number | null | undefined): string => {
    const numeric = toFinite(value);
    if (numeric === null || numeric <= 0) {
        return '';
    }
    return formatBytes(numeric);
};

const buildDisplay = (data: SpeedTestData | null | undefined): DisplayResult | null => {
    if (!data || data.status !== 'ready') {
        return null;
    }
    const estimateMs = toFinite(data.estimatedMs);
    const estimateLabel = estimateMs === null ? '' : formatDuration(estimateMs / 1000);
    const throughputLabel = formatThroughputValue(data.bytesPerSecond);
    const modeValue = data.mode?.trim().toLowerCase() ?? '';
    const factorCandidate = toFinite(data.estimationFactor);
    const factorValue = factorCandidate && factorCandidate > 0 ? factorCandidate : 1;
    const sampleLabel = formatSampleValue(data.sampleBytes);
    return {
        estimateMs,
        estimateLabel,
        throughputLabel,
        mode: modeValue,
        factor: factorValue,
        sampleLabel
    };
};

interface SpeedTestApi {
    hasMeasurement: (data: SpeedTestData | null | undefined) => boolean;
    getEstimateMs: (data: SpeedTestData | null | undefined) => number | null;
    formatEstimate: (data: SpeedTestData | null | undefined) => string;
    formatThroughput: (data: SpeedTestData | null | undefined) => string;
    getMode: (data: SpeedTestData | null | undefined) => string;
    getLoadFactor: (data: SpeedTestData | null | undefined) => number | null;
    formatSample: (data: SpeedTestData | null | undefined) => string;
    getDisplay: (data: SpeedTestData | null | undefined) => DisplayResult | null;
}

const speedTest: SpeedTestApi = Object.freeze({
    hasMeasurement(data: SpeedTestData | null | undefined): boolean {
        return buildDisplay(data) !== null;
    },
    getEstimateMs(data: SpeedTestData | null | undefined): number | null {
        const display = buildDisplay(data);
        return display ? display.estimateMs : null;
    },
    formatEstimate(data: SpeedTestData | null | undefined): string {
        const display = buildDisplay(data);
        return display ? display.estimateLabel : '';
    },
    formatThroughput(data: SpeedTestData | null | undefined): string {
        const display = buildDisplay(data);
        return display ? display.throughputLabel : '';
    },
    getMode(data: SpeedTestData | null | undefined): string {
        const display = buildDisplay(data);
        return display ? display.mode : '';
    },
    getLoadFactor(data: SpeedTestData | null | undefined): number | null {
        const display = buildDisplay(data);
        return display ? display.factor : null;
    },
    formatSample(data: SpeedTestData | null | undefined): string {
        const display = buildDisplay(data);
        return display ? display.sampleLabel : '';
    },
    getDisplay(data: SpeedTestData | null | undefined): DisplayResult | null {
        return buildDisplay(data);
    }
});

export { speedTest, buildDisplay };

export type { SpeedTestData, DisplayResult };

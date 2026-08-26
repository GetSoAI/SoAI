/* SoAI - Charts feature chart point types [frontend/assets/ts/features/charts/data/chartPointTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type ChartSeriesMode = 'value' | 'ohlc';
export type ChartSourceSeriesMode = 'value' | 'ohlc' | 'heikin-ashi';

export interface ChartValuePointInput {
    timestamp: number;
    value: number;
    mode?: string | undefined;
    sourceMode?: string | undefined;
}

export interface ChartOhlcPointInput {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    value?: number | undefined;
    mode?: string | undefined;
    sourceMode?: string | undefined;
}

export type ChartPointInput = ChartValuePointInput | ChartOhlcPointInput;

export interface ChartPointCandidate {
    timestamp?: number | null | undefined;
    value?: number | null | undefined;
    open?: number | null | undefined;
    high?: number | null | undefined;
    low?: number | null | undefined;
    close?: number | null | undefined;
    mode?: string | null | undefined;
    sourceMode?: string | null | undefined;
}

export interface NormalizedDataPoint {
    mode: ChartSeriesMode;
    sourceMode: ChartSourceSeriesMode;
    timestamp: number;
    value: number;
    open: number;
    high: number;
    low: number;
    close: number;
}

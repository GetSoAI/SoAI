/* SoAI - Shared log validation contracts [frontend/assets/ts/core/logvalidation/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

export interface LogEntry {
    timestamp: string;
    component: string;
    level: string;
    message: string;
    text: string;
    metadata?: {
        hostname?: string;
        pid?: number;
    };
    context?: Record<string, JsonValue | null | undefined>;
}

export interface ValidationResult {
    valid: boolean;
    errors: string[];
    entry: LogEntry | null;
}

export interface LogLineLimitResult {
    valid: boolean;
    limit: number | null;
    error: string | null;
}

export interface TextZoomResult {
    valid: boolean;
    zoom: number | null;
    error: string | null;
}

export interface ReplayLimitResult {
    valid: boolean;
    limit: number;
    error: string | null;
}

export interface StrictValidationResult {
    valid: boolean;
    errors: string[];
}

export interface EntriesValidationResult {
    validEntries: LogEntry[];
    invalidEntries: { entry: JsonValue | null | undefined; errors: string[] }[];
}

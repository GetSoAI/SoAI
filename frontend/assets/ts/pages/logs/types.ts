/* SoAI - Logs page contracts [frontend/assets/ts/pages/logs/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogStreamEvent } from '@features/logging/public.ts';

type StreamPayload = LogStreamEvent;

export interface LogStreamService {
    subscribe(callback: (payload: LogStreamEvent) => void, options?: { replayLimit?: number; source?: string }): () => void;
}

export interface LogsUiRefs {
    root: HTMLElement;
    outputContainer: HTMLElement;
    output: HTMLElement;
    emptyState: HTMLElement;
    emptyMessage: HTMLElement;
    sourceSelect: HTMLSelectElement;
    lineLimitSelect: HTMLSelectElement;
}

export type { StreamPayload };

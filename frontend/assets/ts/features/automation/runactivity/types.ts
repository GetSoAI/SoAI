/* SoAI - Automation feature run activity contracts [frontend/assets/ts/features/automation/runactivity/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationRunStatus } from '@core/automation/protocols.ts';

type AutomationRealtimeUpdate = { updateType: 'automation-changed' } | { updateType: 'run-changed'; runId: string } | { updateType: 'connection-lost' } | { updateType: 'connection-restored' };

interface AutomationRunActivitySnapshot {
    initialized: boolean;
    stale: boolean;
    lastSyncedAtMs: number | null;
    hasRunning: boolean;
    runningAutomationIds: ReadonlySet<string>;
}

type AutomationRunActivityListener = (snapshot: AutomationRunActivitySnapshot) => void;
type AutomationRealtimeUpdateListener = (update: AutomationRealtimeUpdate) => void;

interface AutomationRunActivityServiceContract {
    initialize(): Promise<void>;
    subscribe(listener: AutomationRunActivityListener): () => void;
    subscribeRealtime(listener: AutomationRealtimeUpdateListener): () => void;
    getSnapshot(): AutomationRunActivitySnapshot;
}

export type { AutomationRealtimeUpdate, AutomationRealtimeUpdateListener, AutomationRunActivityListener, AutomationRunActivityServiceContract, AutomationRunActivitySnapshot, AutomationRunStatus };

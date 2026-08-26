/* SoAI - Shared frontend connection status public contracts [frontend/assets/ts/core/connectionstatus/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type SubscribeContext = JsonObject & {
    type?: string;
};

interface SnapshotMeta {
    cached: boolean | null;
    source: string | null;
    origin: string | null;
}

interface SystemInfo {
    name: string | null;
    soaiVersion: string | null;
    build: string | null;
    platform: string | null;
    pythonVersion: string | null;
    uptime: number | null;
    port: number | null;
}

interface RestartNotification {
    reason: string;
    path: string | null;
    timestamp: number | null;
}

interface RestartInfo {
    required: boolean;
    timestamp: number | null;
    pid: number | null;
    reasons: string[];
    notifications: RestartNotification[];
}

interface ConnectionHold {
    label: string;
    createdAt: number;
    timer: number | null;
    expiresAtMs?: number;
}

interface ConnectionEvent {
    type: string;
    eventType: string;
    connected: boolean;
    status: JsonObject | null;
    systemInfo: SystemInfo | null;
    restartInfo: RestartInfo;
    raw: JsonValue;
    error: JsonValue;
    attempt: number | null;
    maxAttempts: number | null;
}

interface Waiter {
    resolve: () => void;
    reject: (error: Error) => void;
}

interface StatusSnapshot {
    connected: boolean;
    status: JsonObject;
    systemInfo: SystemInfo | null;
    restartInfo: RestartInfo;
}

type StatusSubscriber = (event: ConnectionEvent) => void;
type RestartSubscriber = (info: RestartInfo) => void;

export type { SubscribeContext, SnapshotMeta, SystemInfo, RestartNotification, RestartInfo, ConnectionHold, ConnectionEvent, Waiter, StatusSnapshot, StatusSubscriber, RestartSubscriber };

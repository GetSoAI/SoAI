/* SoAI - Shared state internal contracts [frontend/assets/ts/core/state/statusmanager/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StatusKey, StatusStreamSnapshot } from '@core/state/statusTypes.ts';
import type { StatusDefinition, StatusDefinitions } from '@core/state/constants.ts';

interface ElementStatus {
    element: HTMLElement;
    status: StatusKey;
    type?: 'indicator' | 'line';
}

interface StatusManagerState {
    definitions: StatusDefinitions;
    defaultStatus: StatusKey;
    allowedColors: string[];
    activeStatuses: Set<StatusKey>;
    errorStatuses: Set<StatusKey>;
    transitionStatuses: Set<StatusKey>;
}

interface PluginState {
    backendNotInstalled: boolean;
    isEnabled: boolean;
    isRunning: boolean;
}

interface ModelState {
    isLoaded: boolean;
    isDownloading: boolean;
    isAvailable: boolean;
}

interface HardwareState {
    error: boolean;
    utilization: number;
}

interface TaskState {
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
}

interface StreamMonitorResult {
    stop: () => void;
}

type SnapshotValue = StatusStreamSnapshot['value'] | undefined;

interface StatusStreamMonitorPayload {
    snapshot: StatusStreamSnapshot;
    rawValue: SnapshotValue;
}

type ErrorLogger = (module: string, message: string, error: Error) => void;
type WarnLogger = (module: string, message: string, detail: JsonValue | null) => void;
type StatusDefinitionLookup = (status: StatusKey) => StatusDefinition;

export type { ElementStatus, StatusManagerState, PluginState, ModelState, HardwareState, TaskState, StreamMonitorResult, SnapshotValue, StatusStreamMonitorPayload, ErrorLogger, WarnLogger, StatusDefinitionLookup };

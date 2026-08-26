/* SoAI - Shared connection state contracts [frontend/assets/ts/core/connectionstate/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ErrorHandler } from '@core/errorHandler.ts';
import type { ConnectionEndpoint } from '@core/connectionstate/connectionEndpoint.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type BaseUrlListener = (value: string | null) => void;

interface ConnectionStateOptions {
    storage: StorageService;
    errorHandler?: ErrorHandler | undefined;
}

interface StorageService {
    get: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    set: (key: string, value: JsonValue | null) => void;
}

interface StateManager {
    getTabState: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    subscribeTabState: (callback: (event: TabStateEvent) => void) => () => void;
}

interface TabStateEvent {
    key: string;
    value: JsonValue | null;
    remote?: boolean;
}

interface Waiter {
    resolve: (value: string) => void;
    reject: (reason: Error) => void;
    cleanup: (() => void) | null;
}

interface UpdateOptions {
    silent?: boolean;
    releaseConfigured?: boolean;
    instanceId?: string | null;
}

interface OnChangeOptions {
    immediate?: boolean;
}

interface WhenReadyOptions {
    signal?: AbortSignal;
}

export type { BaseUrlListener, ConnectionEndpoint, ConnectionStateOptions, StorageService, StateManager, TabStateEvent, Waiter, UpdateOptions, OnChangeOptions, WhenReadyOptions };

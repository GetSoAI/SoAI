/* SoAI - Hardware page realtime state [frontend/assets/ts/pages/hardware/controllers/realtime/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { UnsubscribeTarget } from '@core/realtime/streammanager/service.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { HistorySnapshot } from '@features/hardware/public.ts';

type HardwareHistoryUnsubscribeHandle = {
    unsubscribe: () => void;
};

type HardwareHistoryCloseHandle = {
    close: () => void;
};

type HardwareHistoryManagerHandle = {
    unsubscribe?: (() => void) | undefined;
    close?: (() => void) | undefined;
};

type HardwareHistoryAbortHandle = {
    abort: () => void;
};

type HardwareHistoryStreamHandle = UnsubscribeTarget | HardwareHistoryAbortHandle;

type HardwareHistoryStreamState = {
    historyStreamId: HardwareHistoryStreamHandle;
    historyStreamAbortController: AbortController | null;
    historyRequestToken: symbol | null;
    activeHistoryRequest: { token: symbol; parameters: JsonObject } | null;
    lastHistoryRequest: JsonObject | null;
    historyFetchRequestToken: symbol | null;
    historyStateBackup: HistorySnapshot | null;
    historyStreamInitialized: boolean;
};

const createHardwareHistoryStreamState = (): HardwareHistoryStreamState => ({
    historyStreamId: null,
    historyStreamAbortController: null,
    historyRequestToken: null,
    activeHistoryRequest: null,
    lastHistoryRequest: null,
    historyFetchRequestToken: null,
    historyStateBackup: null,
    historyStreamInitialized: false
});

export { createHardwareHistoryStreamState };
export type { HardwareHistoryAbortHandle, HardwareHistoryCloseHandle, HardwareHistoryManagerHandle, HardwareHistoryStreamHandle, HardwareHistoryStreamState, HardwareHistoryUnsubscribeHandle };

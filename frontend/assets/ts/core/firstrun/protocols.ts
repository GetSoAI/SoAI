/* SoAI - Shared firstrun protocols [frontend/assets/ts/core/firstrun/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

export type FirstRunModalId = 'chatMemoryProfile' | 'dashboardIntro' | 'pluginsIntro';

export type FirstRunPageId = 'chat' | 'dashboard' | 'plugins';

export type FirstRunModalStatus = 'dismissed' | 'completed';

export type FirstRunModalStateEntry = JsonObject & {
    status: FirstRunModalStatus;
    updatedAtMs: number;
};

export type FirstRunModalStateMap = JsonObject & Partial<Record<FirstRunModalId, FirstRunModalStateEntry>>;

export type FirstRunStateStorageValue = JsonValue | null;

export interface FirstRunModalRegistration {
    id: FirstRunModalId;
    pageId: FirstRunPageId;
    modalId: string;
    allowManualOpen: boolean;
    prepare?: ((options?: { signal?: AbortSignal }) => Promise<void>) | undefined;
}

export interface FirstRunStateStorage {
    get: (key: string, defaultValue?: FirstRunStateStorageValue) => FirstRunStateStorageValue;
    set: (key: string, value: FirstRunStateStorageValue) => void;
}

export interface FirstRunModalService {
    handlePageShow(pageId: FirstRunPageId, options?: { signal?: AbortSignal }): Promise<void>;
    open(id: FirstRunModalId, reason: 'auto' | 'manual'): Promise<void>;
    isPending(id: FirstRunModalId): boolean;
}

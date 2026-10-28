/* SoAI - Memory library state and operation contracts [frontend/assets/ts/pages/chat/widgets/memorytab/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManagedMemoryEntry, MemoryLibrary } from '@core/api/contracts/webuiMemoryContracts.ts';
import type { WebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';

type MemoryApi = WebuiUserEndpoints['memory'];
interface MemoryLibraryState {
    snapshot: MemoryLibrary | null;
    phase: 'idle' | 'loading' | 'ready' | 'failed';
    stale: boolean;
    refreshedAt: number | null;
    query: string;
    opening: boolean;
    editorOpen: boolean;
    pending: boolean;
}
interface MemoryMutationHost {
    api: MemoryApi;
    isCurrent(): boolean;
    committed(entry?: ManagedMemoryEntry): void;
    report(error: Error, message?: string): void;
    show(message: string, type: 'error' | 'info' | 'success' | 'warning'): void;
}
export type { MemoryApi, MemoryLibraryState, MemoryMutationHost };

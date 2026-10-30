/* SoAI - Memory mutation authority and failure presentation [frontend/assets/ts/pages/chat/widgets/memorytab/memoryMutationPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { SnapshotError } from '@core/websocketclient/snapshotManager.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { getStreamResources } from '@core/realtime/streammanager/public.ts';
import { MEMORY_LIBRARY } from '@core/realtime/streammanager/resources/ids.ts';
import { hasSameResourceAuthority } from '@core/realtime/streammanager/resources/resourceSnapshotProjection.ts';
import { createDedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import { CHAT_MEMORY_UPDATED_EVENT } from '@features/chat/public.ts';
import type { MemoryApi, MemoryLibraryState, MemoryMutationHost } from '@pages/chat/widgets/memorytab/contracts.ts';
import { memoryFailureMessage } from '@pages/chat/widgets/memorytab/memoryMutationDomain.ts';
import { compareMemoryEntryOrder, memoryMatchesQuery } from '@pages/chat/widgets/memorytab/memoryPresentationDomain.ts';

interface MemoryMutationPresentationHost {
    api: MemoryApi;
    isCurrent(): boolean;
    state(): MemoryLibraryState;
    update(state: MemoryLibraryState): void;
    committed(): void;
    show: MemoryMutationHost['show'];
}

const createMemoryMutationHost = (host: MemoryMutationPresentationHost): MemoryMutationHost => {
    const show: MemoryMutationHost['show'] = (message, type) => {
        if (host.isCurrent()) host.show(message, type);
    };
    const reportUnexpectedFailure = (error: Error): void => {
        if (error instanceof SnapshotError) errorHandler.warn('MemoryLibrary', 'Memory refresh failed', error);
        else if (!(error instanceof APIError)) errorHandler.error('MemoryLibrary', 'Unexpected memory operation failure', error);
    };
    const failures = createDedupingOperationFailureReporter({ host: { showNotification: show, handleError: reportUnexpectedFailure } });
    return {
        api: host.api,
        show,
        isCurrent: host.isCurrent,
        report: (error, message = memoryFailureMessage(error)) => {
            if (!host.isCurrent()) {
                reportUnexpectedFailure(error);
                return;
            }
            if (error instanceof APIError && (error.code === 'memory_revision_changed' || error.code === 'memory_entry_missing')) {
                getStreamResources().invalidate(MEMORY_LIBRARY, 'memory-authority-changed');
                const state = host.state();
                host.update({ ...state, stale: state.snapshot !== null, phase: state.snapshot ? 'ready' : 'failed' });
            }
            failures.report(error, { errorMessage: message, rawMessage: true, context: 'Memory library operation' });
        },
        captureCommitPresentation: () => {
            const captured = getStreamResources().getReconciliationSnapshot(MEMORY_LIBRARY);
            return (entry) => {
                if (!host.isCurrent()) return;
                const project = hasSameResourceAuthority(captured, getStreamResources().getReconciliationSnapshot(MEMORY_LIBRARY));
                host.committed();
                let state = { ...host.state(), stale: true };
                if (project && entry && state.snapshot) state = { ...state, snapshot: { ...state.snapshot, entries: [entry, ...state.snapshot.entries.filter((candidate) => candidate.entity.id !== entry.entity.id)].sort(compareMemoryEntryOrder) } };
                if (project && entry && !memoryMatchesQuery(entry, state.query)) show(i18n.t('chat.memory.library.savedHidden'), 'info');
                host.update(state);
                dispatchCustomEvent(CHAT_MEMORY_UPDATED_EVENT, {});
            };
        }
    };
};

export { createMemoryMutationHost };

/* SoAI - Authenticated layout persistence and restoration write ownership [frontend/assets/ts/core/pagepanes/session.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { capturePagePaneLayout, decodePagePaneLayout, decidePagePaneRestore, inspectPagePaneLayoutOwnership, type PagePaneLayoutIdentity, type PagePaneLayoutRecord, type PagePaneRestoreDecision } from '@core/pagepanes/persistence.ts';
import { PAGE_PANE_RECORD_LIMIT, type PagePaneSlot } from '@core/pagepanes/contracts.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import type { OptionalStorageRead, OptionalStorageRecords } from '@core/storage/service/types.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';

interface PagePaneSessionIdentity extends PagePaneLayoutIdentity {
    readonly authEpoch: number;
}

type PagePanePersistenceStatus = 'inactive' | 'restoring' | 'unsaved' | 'current' | 'restore-failed' | 'invalid' | 'incompatible' | 'foreign' | 'unavailable' | 'quota' | 'blocked' | 'route-limit' | 'record-limit' | 'not-reconstructible' | 'placement';

interface PagePaneLayoutRecovery {
    readonly requiresConfirmation: boolean;
    readonly commit: () => void;
}

interface PagePanePersistenceDependencies {
    readonly storage: OptionalStorageRecords;
    readonly readIdentity: () => PagePaneSessionIdentity | null;
    readonly parseRoute: PageRouting['parseRoute'];
    readonly reportStatus: (status: PagePanePersistenceStatus) => void;
}

interface PagePanePersistenceSession {
    readonly identity: PagePaneSessionIdentity;
    phase: 'restoring' | 'ready' | 'disabled' | 'restore-failed';
    inputRecord: PagePaneLayoutRecord | null;
    lastPersisted: PagePaneLayoutRecord | null;
}

const PAGE_PANE_STORAGE_KEY = 'soai.pagePanes';

class PagePanePersistence {
    readonly #readSlots: () => Iterable<PagePaneSlot>;
    readonly #readFocus: () => string | null;
    readonly #writes = new SequenceToken();
    readonly #changes = new ChangeNotificationSource();
    #dependencies: PagePanePersistenceDependencies | null = null;
    #session: PagePanePersistenceSession | null = null;
    #status: PagePanePersistenceStatus = 'inactive';
    #invalidationFailed = false;
    #invalidating = false;

    constructor(readSlots: () => Iterable<PagePaneSlot>, readFocus: () => string | null) {
        this.#readSlots = readSlots;
        this.#readFocus = readFocus;
    }

    configure(dependencies: PagePanePersistenceDependencies): void {
        if (this.#dependencies) throw new Error('Pane persistence is already configured');
        this.#dependencies = dependencies;
    }

    get status(): PagePanePersistenceStatus {
        return this.#status;
    }

    get restoreRecord(): PagePaneLayoutRecord | null {
        return this.#session?.inputRecord ?? null;
    }

    subscribe(listener: () => void): () => boolean {
        return this.#changes.subscribe(listener);
    }

    get canRecover(): boolean {
        const session = this.#session;
        return !this.#invalidationFailed && !this.#invalidating && session !== null && session.phase !== 'restoring' && this.#isCurrent(session) && this.#status !== 'current';
    }

    #isCurrent(session: PagePanePersistenceSession): boolean {
        const current = this.#dependencies?.readIdentity();
        return this.#session === session && current?.authEpoch === session.identity.authEpoch && current.accountId === session.identity.accountId && current.windowId === session.identity.windowId && current.edition === session.identity.edition;
    }

    #setStatus(status: PagePanePersistenceStatus): void {
        if (this.#status === status) return;
        this.#status = status;
        try {
            this.#changes.notify();
            if (this.#status !== status) return;
            this.#dependencies?.reportStatus(status);
        } catch (error) {
            const failure = ensureError(error);
            if (claimErrorReporting(failure)) errorHandler.error('PagePanePersistence', 'Layout restore status publication failed', failure);
        }
    }

    #unavailable(error: Error | null): void {
        this.#setStatus(error?.name === 'QuotaExceededError' ? 'quota' : error?.name === 'SecurityError' ? 'blocked' : 'unavailable');
    }

    beginRestore(incomingRoute: string | null): PagePaneRestoreDecision {
        const dependencies = this.#dependencies;
        if (!dependencies) throw new Error('Pane persistence requires its configured storage owner');
        const identity = dependencies.readIdentity();
        if (!identity) return { type: 'ordinary', route: incomingRoute };
        const previous = this.#session;
        if (previous && this.#isCurrent(previous)) return previous.phase === 'restoring' ? decidePagePaneRestore(previous.inputRecord, incomingRoute) : { type: 'ordinary', route: incomingRoute };
        const session: PagePanePersistenceSession = { identity: Object.freeze({ ...identity }), phase: 'restoring', inputRecord: null, lastPersisted: null };
        this.#session = session;
        this.#writes.invalidate();
        if (this.#invalidationFailed || this.#invalidating) {
            session.phase = 'disabled';
            this.#setStatus('unavailable');
            return { type: 'ordinary', route: incomingRoute };
        }
        this.#setStatus('restoring');
        if (!this.#isCurrent(session)) return { type: 'ordinary', route: incomingRoute };
        const read = dependencies.storage.readOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, PAGE_PANE_RECORD_LIMIT);
        if (!this.#isCurrent(session)) return { type: 'ordinary', route: incomingRoute };
        if (read.type === 'invalid') {
            if (read.reason === 'size') session.phase = 'disabled';
            this.#setStatus('invalid');
        } else if (read.type === 'unavailable') {
            session.phase = 'disabled';
            this.#unavailable(read.error);
        } else if (read.type === 'value') {
            const decoded = decodePagePaneLayout(read.value, identity, dependencies.parseRoute);
            if (!this.#isCurrent(session)) return { type: 'ordinary', route: incomingRoute };
            if (decoded.type === 'valid') {
                session.inputRecord = decoded.record;
                session.lastPersisted = decoded.record;
            } else {
                if (decoded.type !== 'invalid') session.phase = 'disabled';
                this.#setStatus(decoded.type);
            }
        }
        if (!this.#isCurrent(session)) return { type: 'ordinary', route: incomingRoute };
        return decidePagePaneRestore(session.inputRecord, incomingRoute);
    }

    finishRestore(): void {
        const session = this.#session;
        if (!session || !this.#isCurrent(session) || session.phase === 'disabled') return;
        session.phase = 'ready';
        session.inputRecord = null;
        this.changed();
    }

    failRestore(): void {
        const session = this.#session;
        if (!session || !this.#isCurrent(session) || session.phase !== 'restoring') return;
        session.phase = 'restore-failed';
        this.#setStatus('restore-failed');
    }

    changed(): void {
        const token = this.#writes.next();
        const session = this.#session;
        const dependencies = this.#dependencies;
        if (!session || !dependencies || session.phase !== 'ready' || !this.#isCurrent(session)) return;
        const captured = capturePagePaneLayout(this.#readSlots(), this.#readFocus(), session.identity, dependencies.parseRoute);
        const canMutate = (): boolean => this.#writes.isActive(token) && session.phase === 'ready' && this.#isCurrent(session) && this.#writes.isActive(token);
        if (!canMutate()) return;
        if (captured.type === 'unavailable') {
            this.#setStatus(captured.reason);
            return;
        }
        if (session.lastPersisted && deepEqual(session.lastPersisted, captured.record, { nullishEqual: false })) {
            this.#setStatus('current');
            return;
        }
        this.#setStatus('unsaved');
        if (!canMutate()) return;
        this.#write(captured.record, session, token);
    }

    prepareRecovery(): PagePaneLayoutRecovery | null {
        const session = this.#session;
        const dependencies = this.#dependencies;
        if (!session || !dependencies || !this.canRecover) return null;
        const token = this.#writes.next();
        const captured = capturePagePaneLayout(this.#readSlots(), this.#readFocus(), session.identity, dependencies.parseRoute);
        if (!this.#isCurrent(session) || !this.#writes.isActive(token)) return null;
        if (captured.type === 'unavailable') {
            this.#setStatus(captured.reason);
            return null;
        }
        const stored = dependencies.storage.readOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, PAGE_PANE_RECORD_LIMIT);
        if (!this.#isCurrent(session) || !this.#writes.isActive(token)) return null;
        if (stored.type === 'unavailable') {
            this.#unavailable(stored.error);
            return null;
        }
        const ownership = stored.type === 'value' ? inspectPagePaneLayoutOwnership(stored.value, session.identity).type : null;
        return {
            requiresConfirmation: ownership === 'foreign' || ownership === 'incompatible' || (stored.type === 'invalid' && stored.reason === 'size') || session.phase === 'restore-failed',
            commit: () => {
                if (!this.#isCurrent(session) || !this.#writes.isActive(token) || !this.canRecover) return;
                const current = capturePagePaneLayout(this.#readSlots(), this.#readFocus(), session.identity, dependencies.parseRoute);
                if (current.type !== 'record' || !deepEqual(current.record, captured.record, { nullishEqual: false })) return;
                if (!this.#isCurrent(session) || !this.#writes.isActive(token)) return;
                this.#write(captured.record, session, this.#writes.next(), stored);
            }
        };
    }

    #write(record: PagePaneLayoutRecord, session: PagePanePersistenceSession, token: number, expected?: OptionalStorageRead): void {
        const dependencies = this.#dependencies;
        if (!dependencies) return;
        const canMutate = (): boolean => !this.#invalidationFailed && !this.#invalidating && this.#writes.isActive(token) && this.#isCurrent(session) && this.#writes.isActive(token) && (expected !== undefined || session.phase === 'ready');
        const admitWrite = (): boolean => {
            if (!canMutate()) return false;
            const stored = dependencies.storage.readOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, PAGE_PANE_RECORD_LIMIT);
            if (!canMutate()) return false;
            if (stored.type === 'unavailable') {
                session.phase = 'disabled';
                this.#unavailable(stored.error);
                return false;
            }
            if (expected !== undefined) return deepEqual(stored, expected, { nullishEqual: false }) && canMutate();
            if (stored.type === 'invalid' && stored.reason === 'size') {
                session.phase = 'disabled';
                this.#setStatus('invalid');
                return false;
            }
            if (stored.type === 'value') {
                const ownership = inspectPagePaneLayoutOwnership(stored.value, session.identity);
                if (ownership.type === 'foreign' || ownership.type === 'incompatible') {
                    session.phase = 'disabled';
                    this.#setStatus(ownership.type);
                    return false;
                }
            }
            return canMutate();
        };
        const outcome = dependencies.storage.writeOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, record, PAGE_PANE_RECORD_LIMIT, admitWrite);
        if (!canMutate()) return;
        if (outcome.type === 'written') {
            this.#writes.invalidate();
            session.phase = 'ready';
            session.inputRecord = null;
            session.lastPersisted = record;
            this.#setStatus('current');
        } else if (outcome.type === 'invalid') this.#setStatus(outcome.reason === 'size' ? 'record-limit' : 'invalid');
        else if (outcome.type === 'unavailable') {
            session.phase = 'disabled';
            this.#unavailable(outcome.error);
        }
    }

    invalidate(): void {
        const session = this.#session;
        this.#session = null;
        this.#writes.invalidate();
        if (this.#invalidating) return;
        this.#invalidating = true;
        try {
            if (session && this.#dependencies) {
                const stored = this.#dependencies.storage.readOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, PAGE_PANE_RECORD_LIMIT);
                if (stored.type === 'unavailable') this.#invalidationFailed = true;
                if (stored.type === 'value' && inspectPagePaneLayoutOwnership(stored.value, session.identity).type === 'current') {
                    const outcome = this.#dependencies.storage.removeOptionalRecord('sessionStorage', PAGE_PANE_STORAGE_KEY, () => this.#invalidating);
                    if (outcome.type === 'unavailable') this.#invalidationFailed = true;
                }
            }
        } finally {
            this.#invalidating = false;
        }
        if (this.#session === null) this.#setStatus(this.#invalidationFailed ? 'unavailable' : 'inactive');
    }

    captureInvalidation(): () => void {
        const session = this.#session;
        return () => {
            if (this.#session === session) this.invalidate();
        };
    }
}

export { PagePanePersistence, PAGE_PANE_STORAGE_KEY };
export type { PagePanePersistenceDependencies, PagePaneSessionIdentity, PagePanePersistenceStatus };

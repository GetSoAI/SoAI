/* SoAI - Native modal presentation reservations and release completion [frontend/assets/ts/core/modals/modalhost/ownership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures, type Cleanup } from '@core/lifecycle/cleanup.ts';
import { normalizeModalId } from '@core/modals/guards.ts';
import type { ModalHostState, ModalOwnershipLifetime } from '@core/modals/modalhost/contracts.ts';
import type { ModalOwnership, ModalReleaseOutcome } from '@core/modals/types.ts';
import { requirePresentationOwnerActive } from '@core/presentationOwner.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isThenable } from '@core/typeGuards.ts';

const acquireModalOwnership = (state: ModalHostState, id: string, owner: PresentationOwner, disposeSession: Cleanup | null = null): ModalOwnership => {
    const modalId = normalizeModalId(id);
    requirePresentationOwnerActive(owner);
    if (state.ownership.has(modalId)) throw new Error('Modal presentation is already owned');
    state.resources.requireActive();
    const controller = new AbortController();
    const completion = createDeferred<ModalReleaseOutcome>();
    const ownership: ModalOwnership = Object.freeze({ modalId, owner, generation: Symbol(modalId), signal: controller.signal, completion: completion.promise });
    const cleanup = async (): Promise<void> => {
        releaseModalOwnership(state, ownership);
        const outcome = await completion.promise;
        if (outcome.type === 'failed') throw outcome.error;
    };
    const lifetime: ModalOwnershipLifetime = { controller, completion, disposeObservation: null, disposeSession, cleanup, type: owner.type === 'global' ? 'active' : 'acquiring' };
    state.ownership.set(modalId, ownership);
    state.ownershipLifetimes.set(ownership, lifetime);
    try {
        state.resources.track(cleanup, (release) => release());
        if (owner.type !== 'global') {
            const unsubscribe = owner.presentation.subscribe(() => {
                if (state.ownership.get(modalId) !== ownership || controller.signal.aborted || owner.admission.isCurrent()) return;
                try {
                    state.onOwnershipRevoked(ownership);
                } catch (error) {
                    errorHandler.warn('ModalHost', 'Revoked modal cleanup is incomplete', ensureError(error));
                }
            });
            lifetime.disposeObservation = unsubscribe;
            state.ownershipLifetimes.set(ownership, { ...lifetime, type: 'active' });
            if (controller.signal.aborted) releaseModalOwnership(state, ownership);
        }
        requireModalOwnership(state, ownership);
    } catch (error) {
        const failure = ensureError(error);
        const failures = [failure];
        const current = state.ownershipLifetimes.get(ownership);
        if (current?.type === 'acquiring') state.ownershipLifetimes.set(ownership, { ...current, type: 'active' });
        try {
            releaseModalOwnership(state, ownership, current?.type === 'acquiring' ? failures : []);
        } catch (releaseError) {
            const releaseFailure = ensureError(releaseError);
            if (!failures.includes(releaseFailure)) failures.push(releaseFailure);
        }
        throwCollectedCleanupFailures(failures);
        throw failure;
    }
    return ownership;
};

const requireModalOwnership = (state: ModalHostState, ownership: ModalOwnership): void => {
    if (state.ownership.get(ownership.modalId) !== ownership || ownership.signal.aborted) throw createAbortError('Modal presentation was superseded');
    requirePresentationOwnerActive(ownership.owner);
};

const releaseModalOwnershipObservation = (state: ModalHostState, ownership: ModalOwnership): void => {
    const lifetime = state.ownershipLifetimes.get(ownership);
    if (!lifetime?.disposeObservation) return;
    const dispose = lifetime.disposeObservation;
    lifetime.disposeObservation = null;
    dispose();
};

const releaseModalOwnership = (state: ModalHostState, ownership: ModalOwnership, initialFailures: readonly Error[] = []): boolean => {
    if (state.ownership.get(ownership.modalId) !== ownership || state.activeStack.includes(ownership.modalId)) return false;
    const lifetime = state.ownershipLifetimes.get(ownership);
    if (!lifetime) throw new Error('Modal ownership lifetime is missing');
    if (lifetime.type === 'failed') throw lifetime.error;
    if (lifetime.type === 'releasing') return false;
    if (lifetime.type === 'acquiring') {
        if (!lifetime.controller.signal.aborted) lifetime.controller.abort();
        return false;
    }
    const releasing: ModalOwnershipLifetime = { ...lifetime, type: 'releasing' };
    state.ownershipLifetimes.set(ownership, releasing);
    const failures: Error[] = [...initialFailures];
    const complete = (): boolean => {
        try {
            throwCollectedCleanupFailures(failures);
        } catch (error) {
            const failure = ensureError(error);
            state.ownershipLifetimes.set(ownership, { ...releasing, type: 'failed', error: failure });
            lifetime.completion.resolve({ type: 'failed', error: failure });
            return false;
        }
        state.resources.untrack(lifetime.cleanup);
        if (state.ownership.get(ownership.modalId) === ownership) state.ownership.delete(ownership.modalId);
        state.ownershipLifetimes.delete(ownership);
        lifetime.completion.resolve({ type: 'released' });
        return true;
    };
    runCleanupStepCollectingFailure(() => lifetime.controller.abort(), failures);
    runCleanupStepCollectingFailure(() => releaseModalOwnershipObservation(state, ownership), failures);
    let sessionRelease: void | Promise<void> = undefined;
    try {
        sessionRelease = lifetime.disposeSession?.();
    } catch (error) {
        failures.push(ensureError(error));
    }
    if (isThenable(sessionRelease)) {
        void Promise.resolve(sessionRelease).then(
            () => complete(),
            (error) => {
                failures.push(ensureError(error));
                complete();
            }
        );
        return false;
    }
    const released = complete();
    throwCollectedCleanupFailures(failures);
    return released;
};

const hasOpenModalsOutsideOwners = (state: ModalHostState, excludedOwners: readonly PresentationOwner[]): boolean =>
    state.activeStack.some((modalId) => {
        const ownership = state.ownership.get(modalId);
        return !ownership || !excludedOwners.includes(ownership.owner);
    });

export { acquireModalOwnership, releaseModalOwnershipObservation, releaseModalOwnership, requireModalOwnership, hasOpenModalsOutsideOwners };

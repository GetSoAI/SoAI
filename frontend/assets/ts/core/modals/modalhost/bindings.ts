/* SoAI - Native modal binding acquisition and release lifetime [frontend/assets/ts/core/modals/modalhost/bindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { Cleanup } from '@core/lifecycle/cleanup.ts';
import type { ModalReleaseOutcome } from '@core/modals/types.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isFunction, isObject, isThenable } from '@core/typeGuards.ts';

type ModalBinder = { dispose: Cleanup };
type ModalBindingState = { type: 'acquiring'; releaseRequested: boolean } | { type: 'active'; binder: ModalBinder } | { type: 'releasing'; binder: ModalBinder } | { type: 'released' } | { type: 'failed'; binder: ModalBinder; error: Error };
type ModalBinding = { state: ModalBindingState; completion: ReturnType<typeof createDeferred<ModalReleaseOutcome>> };

const releaseModalBinding = (binding: ModalBinding): Promise<ModalReleaseOutcome> => {
    const state = binding.state;
    if (state.type === 'acquiring') state.releaseRequested = true;
    if (state.type !== 'active') return binding.completion.promise;
    binding.state = { type: 'releasing', binder: state.binder };
    const settle = (outcome: ModalReleaseOutcome): void => {
        binding.state = outcome.type === 'failed' ? { ...outcome, binder: state.binder } : outcome;
        binding.completion.resolve(outcome);
    };
    try {
        const result = state.binder.dispose();
        if (isThenable(result)) {
            void Promise.resolve(result).then(
                () => settle({ type: 'released' }),
                (error) => settle({ type: 'failed', error: ensureError(error) })
            );
        } else settle({ type: 'released' });
    } catch (error) {
        settle({ type: 'failed', error: ensureError(error) });
    }
    return binding.completion.promise;
};

const bindModalElement = (bindings: Map<string, ModalBinding>, modal: HTMLElement, bind: (modal: HTMLElement) => ModalBinder, canAcquire: () => boolean): void => {
    if (bindings.has(modal.id)) throw new Error('Modal binding is already owned');
    const acquisition = { type: 'acquiring', releaseRequested: false } satisfies ModalBindingState;
    const binding: ModalBinding = { state: acquisition, completion: createDeferred<ModalReleaseOutcome>() };
    bindings.set(modal.id, binding);
    try {
        const binder = bind(modal);
        if (!isObject(binder) || !isFunction(binder.dispose)) throw new Error(`Modal "${modal.id}" bind() must return a disposer`);
        binding.state = { type: 'active', binder };
        if (!acquisition.releaseRequested && canAcquire()) return;
        releaseModalBinding(binding);
        throw createAbortError('Modal binding acquisition was cancelled');
    } catch (error) {
        if (binding.state.type === 'acquiring') {
            binding.state = { type: 'released' };
            binding.completion.resolve({ type: 'released' });
            if (bindings.get(modal.id) === binding) bindings.delete(modal.id);
        }
        throw error;
    }
};

const requireModalBindingSettled = (binding: ModalBinding): void => {
    if (binding.state.type === 'failed') throw binding.state.error;
    if (binding.state.type !== 'active' && binding.state.type !== 'released') throw new Error('Modal binding release is unconfirmed');
};

export { bindModalElement, releaseModalBinding, requireModalBindingSettled };
export type { ModalBinder, ModalBinding };

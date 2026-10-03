/* SoAI - Shared storage AI setup state actions [frontend/assets/ts/core/storage/service/aiSetupActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { decodeAiSetupState, serializeAiSetupState } from '@core/storage/aisetup/aiSetupCodec.ts';
import { isAiSetupStateResumable, type AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

type AiSetupStateUpdate = (current: AiSetupState | null) => AiSetupState | null;

const createAiSetupStateMethods = (core: StorageRuntime): { getAiSetup: () => AiSetupState | null; updateAiSetup: (update: AiSetupStateUpdate) => AiSetupState | null; isAiSetupResumable: () => boolean } => {
    const state = core.state;
    const getAiSetup = (): AiSetupState | null => core.clone(state.cache.wizard.aiSetup);
    const updateAiSetup = (update: AiSetupStateUpdate): AiSetupState | null => {
        const serialized = serializeAiSetupState(update(getAiSetup()));
        const next = serialized === null ? null : decodeAiSetupState(serialized);
        if (serialized !== null && next === null) {
            throw new Error('AI setup state update is invalid');
        }
        state.cache.wizard.aiSetup = next;
        core.scheduleBroadcast();
        terminateHandledPromise(core.queuePersist('wizard'));
        return core.clone(next);
    };
    const isAiSetupResumable = (): boolean => isAiSetupStateResumable(state.cache.wizard.aiSetup);
    return { getAiSetup, updateAiSetup, isAiSetupResumable };
};

export { createAiSetupStateMethods };
export type { AiSetupStateUpdate };

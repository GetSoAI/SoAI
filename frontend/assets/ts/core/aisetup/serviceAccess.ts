/* SoAI - Kernel accessor for the AI setup attention service [frontend/assets/ts/core/aisetup/serviceAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AI_SETUP_ATTENTION_SERVICE_ID, type AiSetupAttentionLifecycleContract } from '@core/aisetup/protocols.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';

const isAiSetupAttentionLifecycle = <T>(value: T): value is T & AiSetupAttentionLifecycleContract => isObject(value) && hasFunctionProperty(value, 'initialize') && hasFunctionProperty(value, 'dispose');

const requireAiSetupAttentionLifecycle = (): AiSetupAttentionLifecycleContract => {
    const service = resolveKernelService(AI_SETUP_ATTENTION_SERVICE_ID);
    if (!isAiSetupAttentionLifecycle(service)) {
        throw new Error(`${AI_SETUP_ATTENTION_SERVICE_ID} must expose initialize() and dispose()`);
    }
    return service;
};

export { requireAiSetupAttentionLifecycle };

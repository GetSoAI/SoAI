/* SoAI - Kernel accessors for automation run activity services [frontend/assets/ts/core/automation/serviceAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTOMATION_RUN_ACTIVITY_SERVICE_ID, type AutomationRunActivityLifecycleContract, type AutomationRunActivitySubscribeContract } from '@core/automation/protocols.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface AutomationRunActivitySubscribeCandidate {
    subscribe?: AutomationRunActivitySubscribeContract['subscribe'];
}

interface AutomationRunActivityLifecycleCandidate {
    initialize?: AutomationRunActivityLifecycleContract['initialize'];
    destroy?: AutomationRunActivityLifecycleContract['destroy'];
}

const isObjectValue = <T>(value: T): boolean => typeof value === 'object' && value !== null;

const isFunctionValue = <T>(value: T): boolean => typeof value === 'function';

const isAutomationRunActivitySubscribeCandidate = <T>(value: T): value is T & AutomationRunActivitySubscribeCandidate => isObjectValue(value);

const isAutomationRunActivityLifecycleCandidate = <T>(value: T): value is T & AutomationRunActivityLifecycleCandidate => isObjectValue(value);

const isAutomationRunActivitySubscribeContract = <T>(value: T): value is T & AutomationRunActivitySubscribeContract => {
    return isAutomationRunActivitySubscribeCandidate(value) && isFunctionValue(value.subscribe);
};

const isAutomationRunActivityLifecycleContract = <T>(value: T): value is T & AutomationRunActivityLifecycleContract => {
    return isAutomationRunActivityLifecycleCandidate(value) && isFunctionValue(value.initialize) && isFunctionValue(value.destroy);
};

const requireAutomationRunActivitySubscribe = (): AutomationRunActivitySubscribeContract => {
    const service = resolveKernelService(AUTOMATION_RUN_ACTIVITY_SERVICE_ID);
    if (!isAutomationRunActivitySubscribeContract(service)) {
        throw new Error(`${AUTOMATION_RUN_ACTIVITY_SERVICE_ID} must expose subscribe()`);
    }
    return service;
};

const requireAutomationRunActivityLifecycle = (): AutomationRunActivityLifecycleContract => {
    const service = resolveKernelService(AUTOMATION_RUN_ACTIVITY_SERVICE_ID);
    if (!isAutomationRunActivityLifecycleContract(service)) {
        throw new Error(`${AUTOMATION_RUN_ACTIVITY_SERVICE_ID} must expose initialize() and destroy()`);
    }
    return service;
};

export { requireAutomationRunActivityLifecycle, requireAutomationRunActivitySubscribe };

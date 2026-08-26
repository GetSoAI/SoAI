/* SoAI - Shared frontend service registration [frontend/assets/ts/core/serviceRegistration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';

interface RegisterOptions {
    moduleId?: string;
    registeredAt?: number;
    initialized?: boolean;
    initializedAt?: number;
}

const assertCanonicalServiceId = (value: string): string => {
    const normalized = assertNonEmptyString(value, 'registerService: id');
    if (normalized.startsWith('core.') || normalized.startsWith('features.') || normalized.startsWith('pages.')) {
        return normalized;
    }
    throw new Error(`registerService: service id must be canonical (core.*, features.*, pages.*). Got '${normalized}'`);
};

function registerService<TServiceName extends SoAIServiceId>(id: TServiceName, instance: SoAIServiceRegistry[TServiceName], options?: RegisterOptions): string;
function registerService(id: string, instance: SoAIRegisteredService, options?: RegisterOptions): string;
function registerService(id: string, instance: SoAIRegisteredService, options: RegisterOptions = {}): string {
    const canonicalId = assertCanonicalServiceId(id);

    if (isNullOrUndefined(instance)) {
        throw new Error(`registerService: instance cannot be null or undefined for service '${canonicalId}'`);
    }

    getServiceContainer().register(canonicalId, instance, options);
    return canonicalId;
}
export { registerService };

export type { RegisterOptions };

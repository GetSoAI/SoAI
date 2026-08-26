/* SoAI - Shared frontend SoAI OS access [frontend/assets/ts/core/soaiOsAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isObject, isPlainObject } from '@core/typeGuards.ts';
import type { OsCapabilities } from '@core/api/contracts/osSystemContractTypes.ts';

type SoaiOsAccessState = 'unknown' | 'granted' | 'denied' | 'unavailable';
const SOAI_OS_CAPABILITIES_SERVICE_ID = 'core.soaiOsCapabilities';

interface SoaiOsCapabilitiesSnapshot {
    initialized: boolean;
    osModeEnabled: boolean;
    osAccessible: boolean;
    accessState: SoaiOsAccessState;
    capabilities: OsCapabilities | null;
    lastError: string | null;
}

interface SoaiOsCapabilitiesService {
    getSnapshot: () => SoaiOsCapabilitiesSnapshot;
    onChange: (listener: (snapshot: SoaiOsCapabilitiesSnapshot) => void, options?: { immediate?: boolean }) => (() => void) | undefined;
    ensureReady: (options?: { timeoutMs?: number }) => Promise<void>;
    refreshAccess: () => Promise<void>;
    clearAccess: () => void;
}

const isSoaiOsAccessState = (value: string | null | undefined): value is SoaiOsAccessState => value === 'unknown' || value === 'granted' || value === 'denied' || value === 'unavailable';

const isSoaiOsCapabilitiesSnapshot = (value: Partial<SoaiOsCapabilitiesSnapshot> | null | undefined): value is SoaiOsCapabilitiesSnapshot => {
    if (!isPlainObject(value)) return false;
    const accessState = value.accessState;
    const capabilities = value.capabilities;
    const lastError = value.lastError;
    return typeof value.initialized === 'boolean' && typeof value.osModeEnabled === 'boolean' && typeof value.osAccessible === 'boolean' && typeof accessState === 'string' && isSoaiOsAccessState(accessState) && (capabilities === null || isPlainObject(capabilities)) && (lastError === null || typeof lastError === 'string');
};

const isSoaiOsCapabilitiesService = <T>(value: T): value is T & SoaiOsCapabilitiesService => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'getSnapshot') && hasFunctionProperty(value, 'onChange') && hasFunctionProperty(value, 'ensureReady') && hasFunctionProperty(value, 'refreshAccess') && hasFunctionProperty(value, 'clearAccess');
};

const resolveSoaiOsCapabilitiesSnapshotRequired = (): SoaiOsCapabilitiesSnapshot => {
    if (!hasKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID} service must be registered`);
    }
    const candidate = resolveKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID);
    if (!isSoaiOsCapabilitiesService(candidate)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID} must expose getSnapshot(), onChange(), ensureReady(), refreshAccess(), and clearAccess()`);
    }
    const snapshot = candidate.getSnapshot();
    if (!isSoaiOsCapabilitiesSnapshot(snapshot)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID}.getSnapshot() must return a valid snapshot`);
    }
    return snapshot;
};

const resolveSoaiOsCapabilitiesServiceRequired = (): SoaiOsCapabilitiesService => {
    if (!hasKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID} service must be registered`);
    }
    const candidate = resolveKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID);
    if (!isSoaiOsCapabilitiesService(candidate)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID} must expose getSnapshot(), onChange(), ensureReady(), refreshAccess(), and clearAccess()`);
    }
    return candidate;
};

const isSoaiOsNavigationAvailable = (snapshot: SoaiOsCapabilitiesSnapshot): boolean => snapshot.osModeEnabled && snapshot.osAccessible && snapshot.accessState === 'granted';

const resolveSoaiOsNavigationAvailability = (): boolean => isSoaiOsNavigationAvailable(resolveSoaiOsCapabilitiesSnapshotRequired());

const requireSoaiOsCapabilitiesSnapshot = (snapshot: SoaiOsCapabilitiesSnapshot): SoaiOsCapabilitiesSnapshot => snapshot;

const subscribeToSoaiOsCapabilitiesChanges = (listener: (snapshot: SoaiOsCapabilitiesSnapshot) => void, options: { immediate?: boolean } = {}): (() => void) => {
    const service = resolveSoaiOsCapabilitiesServiceRequired();
    const unsubscribe = service.onChange((snapshot) => listener(requireSoaiOsCapabilitiesSnapshot(snapshot)), options);
    if (typeof unsubscribe !== 'function') {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID}.onChange() must return an unsubscribe function`);
    }
    return unsubscribe;
};

export { SOAI_OS_CAPABILITIES_SERVICE_ID, isSoaiOsAccessState, isSoaiOsCapabilitiesService, isSoaiOsCapabilitiesSnapshot, isSoaiOsNavigationAvailable, resolveSoaiOsCapabilitiesServiceRequired, resolveSoaiOsCapabilitiesSnapshotRequired, resolveSoaiOsNavigationAvailability, subscribeToSoaiOsCapabilitiesChanges };
export type { SoaiOsAccessState, SoaiOsCapabilitiesService, SoaiOsCapabilitiesSnapshot };

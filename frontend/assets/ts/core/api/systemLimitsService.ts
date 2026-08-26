/* SoAI - Shared API system limits service [frontend/assets/ts/core/api/systemLimitsService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiClient } from '@core/api/service.ts';
import { readTtlStorageEntry, readTtlStorageValue, removeStorageKey, writeTtlStorageValue } from '@core/storage/ttlStorageCache.ts';
import { decodeSystemLimits, serializeSystemLimitsCache, type SystemLimits } from '@core/api/contracts/systemLimitsContracts.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { hoursToMs } from '@core/time/durations.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const CACHE_TTL_MS = hoursToMs(1);
const STORAGE_KEY = 'soai.system.limits';

const isSystemLimitsWire = <T>(data: T): data is T & JsonObject => {
    if (!isJsonObject(data)) {
        return false;
    }
    const maxBytes = data['max_file_upload_bytes'];
    const maxMb = data['max_file_upload_mb'];
    const cameraVisionUploadEnabled = data['camera_vision_upload_enabled'];
    const cameraVisionImageOptimizationEnabled = data['camera_vision_image_optimization_enabled'];
    return typeof maxBytes === 'number' && typeof maxMb === 'number' && typeof cameraVisionUploadEnabled === 'boolean' && typeof cameraVisionImageOptimizationEnabled === 'boolean';
};

class SystemLimitsService {
    #cachedLimits: SystemLimits | null = null;
    #cacheTimestamp = 0;
    #fetchPromise: Promise<SystemLimits> | null = null;

    async fetchSystemLimits(): Promise<SystemLimits> {
        const now = Date.now();
        if (this.#cachedLimits && now - this.#cacheTimestamp < CACHE_TTL_MS) {
            return this.#cachedLimits;
        }

        const stored = readTtlStorageEntry<JsonObject>('localStorage', STORAGE_KEY, CACHE_TTL_MS, isSystemLimitsWire);
        if (stored) {
            const storedLimits = decodeSystemLimits(stored.value);
            this.#cachedLimits = storedLimits;
            this.#cacheTimestamp = stored.timestamp;
            return storedLimits;
        }

        if (this.#fetchPromise) {
            return this.#fetchPromise;
        }

        this.#fetchPromise = this.#doFetch();

        try {
            const limits = await this.#fetchPromise;
            this.#cachedLimits = limits;
            this.#cacheTimestamp = Date.now();
            writeTtlStorageValue('localStorage', STORAGE_KEY, serializeSystemLimitsCache(limits));
            return limits;
        } finally {
            this.#fetchPromise = null;
        }
    }

    async #doFetch(): Promise<SystemLimits> {
        return getApiClient().system.limits();
    }

    #readStoredLimits(): SystemLimits | null {
        const stored = readTtlStorageValue<JsonObject>('localStorage', STORAGE_KEY, CACHE_TTL_MS, isSystemLimitsWire);
        return stored ? decodeSystemLimits(stored) : null;
    }

    getMaxFileUploadBytes(): number {
        if (this.#cachedLimits) {
            return this.#cachedLimits.maxFileUploadBytes;
        }
        const stored = this.#readStoredLimits();
        if (stored) return stored.maxFileUploadBytes;
        throw new Error('System limits not loaded. Call fetchSystemLimits() first.');
    }

    getCameraVisionUploadEnabled(): boolean {
        if (this.#cachedLimits) {
            return this.#cachedLimits.cameraVisionUploadEnabled;
        }
        const stored = this.#readStoredLimits();
        if (stored) return stored.cameraVisionUploadEnabled;
        throw new Error('System limits not loaded. Call fetchSystemLimits() first.');
    }

    getCameraVisionImageOptimizationEnabled(): boolean {
        if (this.#cachedLimits) {
            return this.#cachedLimits.cameraVisionImageOptimizationEnabled;
        }
        const stored = this.#readStoredLimits();
        if (stored) return stored.cameraVisionImageOptimizationEnabled;
        throw new Error('System limits not loaded. Call fetchSystemLimits() first.');
    }

    clearCache(): void {
        this.#cachedLimits = null;
        this.#cacheTimestamp = 0;
        removeStorageKey('localStorage', STORAGE_KEY);
    }
}

const SYSTEM_LIMITS_SERVICE_ID = 'core.systemLimitsService';

const createSystemLimitsService = (): SystemLimitsService => new SystemLimitsService();

const getSystemLimitsService = (): SystemLimitsService => {
    const candidate = resolveKernelService(SYSTEM_LIMITS_SERVICE_ID);
    if (!(candidate instanceof SystemLimitsService)) {
        throw new Error(`${SYSTEM_LIMITS_SERVICE_ID} is not registered`);
    }
    return candidate;
};

const fetchSystemLimits = (): Promise<SystemLimits> => getSystemLimitsService().fetchSystemLimits();

const getMaxFileUploadBytes = (): number => getSystemLimitsService().getMaxFileUploadBytes();

const getCameraVisionUploadEnabled = (): boolean => getSystemLimitsService().getCameraVisionUploadEnabled();

const getCameraVisionImageOptimizationEnabled = (): boolean => getSystemLimitsService().getCameraVisionImageOptimizationEnabled();

export { fetchSystemLimits, getCameraVisionImageOptimizationEnabled, getCameraVisionUploadEnabled, getMaxFileUploadBytes, getSystemLimitsService, createSystemLimitsService, SYSTEM_LIMITS_SERVICE_ID, SystemLimitsService };
export type { SystemLimits };

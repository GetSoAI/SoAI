/* SoAI - Identity-aware backend discovery service [frontend/assets/ts/core/discoveryservice/DiscoveryService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { probeFetch } from '@core/api/probeFetch.ts';
import { DEFAULT_API_PORT, DISCOVERY_PORTS, DISCOVERY_TIMEOUT_MS, HEALTH_PROBE_PATH, READY_EVENT } from '@core/discoveryservice/constants.ts';
import { decodeRuntimeEndpointHealthPayload, decodeRuntimeEndpointPayload } from '@core/discoveryservice/runtimeEndpointPayload.ts';
import { selectDiscoveredEndpoint, type DiscoveredEndpoint } from '@core/discoveryservice/selection.ts';
import { dispatchCustomEvent, getLocation, getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import { getDiscoveryPorts } from '@core/runtimeconfiguration/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { assertBackendEdition, isBackendEditionIntegrityError } from '@core/edition/backendEditionIntegrity.ts';

class DiscoveryService {
    #activeControllers = new Set<AbortController>();
    #discoveredEndpoint: DiscoveredEndpoint | null = null;
    #discoveryKey: string | null = null;
    #discoveryPromise: Promise<DiscoveredEndpoint> | null = null;

    async discoverEndpoint(hostname?: string, targetInstanceId: string | null = null): Promise<DiscoveredEndpoint> {
        if (this.#discoveredEndpoint && (!targetInstanceId || this.#discoveredEndpoint.instanceId === targetInstanceId)) {
            return this.#discoveredEndpoint;
        }
        const locationRef = getLocation();
        const targetHostname = isString(hostname) && hostname.trim() ? hostname.trim() : locationRef.hostname;
        if (!targetHostname) {
            throw new Error('Target hostname is unavailable');
        }
        const discoveryKey = `${targetHostname}\n${locationRef.protocol}\n${locationRef.port}\n${targetInstanceId ?? ''}`;
        const activeDiscovery = this.#discoveryPromise;
        if (activeDiscovery) {
            if (this.#discoveryKey === discoveryKey) {
                return activeDiscovery;
            }
            try {
                await activeDiscovery;
            } catch (error) {
                ensureError(error);
            }
            return this.discoverEndpoint(targetHostname, targetInstanceId);
        }
        const discoveryTask = this.#discover(targetHostname, locationRef.protocol, locationRef.port, targetInstanceId);
        this.#discoveryPromise = discoveryTask;
        this.#discoveryKey = discoveryKey;
        try {
            return await discoveryTask;
        } finally {
            if (this.#discoveryPromise === discoveryTask) {
                this.#discoveryPromise = null;
                this.#discoveryKey = null;
            }
        }
    }

    async #discover(hostname: string, locationProtocol: string, locationPort: string, targetInstanceId: string | null): Promise<DiscoveredEndpoint> {
        const protocol = locationProtocol === 'https:' ? 'https' : 'http';
        const directPorts: number[] = [];
        const parsedLocationPort = Number.parseInt(locationPort, 10);
        if (Number.isInteger(parsedLocationPort) && parsedLocationPort > 0 && parsedLocationPort <= 65535) {
            directPorts.push(parsedLocationPort);
        } else {
            directPorts.push(DEFAULT_API_PORT);
        }
        for (const port of directPorts) {
            const endpoint = await this.#probeHealth(hostname, protocol, port);
            if (endpoint && (!targetInstanceId || endpoint.instanceId === targetInstanceId)) {
                this.#discoveredEndpoint = endpoint;
                this.#abortControllers();
                return endpoint;
            }
        }
        const discoveryPorts = this.getCandidatePorts();
        const candidates = (await Promise.all(discoveryPorts.map((port) => this.#probeDiscoveryPort(hostname, protocol, port)))).filter((endpoint): endpoint is DiscoveredEndpoint => endpoint !== null);
        const selection = selectDiscoveredEndpoint(candidates, targetInstanceId);
        if (selection.type === 'selected') {
            this.#discoveredEndpoint = selection.endpoint;
            this.#abortControllers();
            return selection.endpoint;
        }
        this.#abortControllers();
        if (selection.type === 'ambiguous') {
            throw new Error('Multiple SoAI instances were discovered; select an explicit endpoint');
        }
        throw new Error('No verified SoAI endpoint was discovered');
    }

    async #probeDiscoveryPort(hostname: string, protocol: 'http' | 'https', port: number): Promise<DiscoveredEndpoint | null> {
        const discoveryPayload = await this.#fetchPayload(`${protocol}://${hostname}:${port}/`);
        if (!discoveryPayload) {
            return null;
        }
        let advertised;
        try {
            advertised = decodeRuntimeEndpointPayload(discoveryPayload);
            assertBackendEdition(advertised.edition);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isBackendEditionIntegrityError(runtimeError)) throw runtimeError;
            errorHandler.debug('DiscoveryService', 'Discovery response runtime endpoint contract was invalid', runtimeError);
            return null;
        }
        const endpoint = await this.#probeHealth(hostname, advertised.scheme, advertised.port);
        if (!endpoint) {
            return null;
        }
        if (endpoint.instanceId !== advertised.instanceId || endpoint.scheme !== advertised.scheme || endpoint.port !== advertised.port || endpoint.preferredPort !== advertised.preferredPort || endpoint.fallbackActive !== advertised.fallbackActive || endpoint.edition !== advertised.edition) {
            return null;
        }
        return endpoint;
    }

    getCandidatePorts(): number[] {
        const configuredPorts = getDiscoveryPorts();
        for (const port of configuredPorts) {
            if (!isNumber(port) || !Number.isInteger(port) || port < 1 || port > 65535) {
                throw new Error(`Runtime configuration returned an invalid discovery port: ${port}`);
            }
        }
        return Array.from(new Set([...configuredPorts, ...DISCOVERY_PORTS]));
    }

    async #probeHealth(hostname: string, scheme: 'http' | 'https', port: number): Promise<DiscoveredEndpoint | null> {
        const payload = await this.#fetchPayload(`${scheme}://${hostname}:${port}${HEALTH_PROBE_PATH}`);
        if (!payload) {
            return null;
        }
        try {
            const endpoint = decodeRuntimeEndpointHealthPayload(payload);
            assertBackendEdition(endpoint.edition);
            if (endpoint.scheme !== scheme || endpoint.port !== port) {
                return null;
            }
            return { ...endpoint, baseUrl: `${scheme}://${hostname}:${port}` };
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isBackendEditionIntegrityError(runtimeError)) throw runtimeError;
            errorHandler.debug('DiscoveryService', 'API health response runtime endpoint contract was invalid', runtimeError);
            return null;
        }
    }

    async #fetchPayload(url: string): Promise<JsonObject | null> {
        const controller = new AbortController();
        this.#activeControllers.add(controller);
        const windowRef = getWindow();
        const timeoutId = windowRef.setTimeout(() => controller.abort(), DISCOVERY_TIMEOUT_MS);
        try {
            const response = await probeFetch(url, { signal: controller.signal, acceptJson: true });
            if (!response.ok) {
                return null;
            }
            const payload = parseRequiredJsonText(await response.clone().text());
            return isObject(payload) ? payload : null;
        } catch (error) {
            errorHandler.debug('DiscoveryService', `Endpoint probe failed for ${url}`, ensureError(error));
            return null;
        } finally {
            windowRef.clearTimeout(timeoutId);
            this.#activeControllers.delete(controller);
        }
    }

    #abortControllers(): void {
        for (const controller of Array.from(this.#activeControllers)) {
            controller.abort();
            this.#activeControllers.delete(controller);
        }
    }

    reset(): void {
        this.#abortControllers();
        this.#discoveredEndpoint = null;
        this.#discoveryKey = null;
        this.#discoveryPromise = null;
    }

    getEdition(): 'soai-core' | 'soai-os' | null {
        return this.#discoveredEndpoint?.edition ?? null;
    }
}

let discoveryServiceInstance: DiscoveryService | null = null;

const getDiscoveryService = (): DiscoveryService => {
    if (!discoveryServiceInstance) {
        discoveryServiceInstance = new DiscoveryService();
        dispatchCustomEvent(READY_EVENT, discoveryServiceInstance);
    }
    return discoveryServiceInstance;
};

export { DiscoveryService, READY_EVENT, getDiscoveryService };

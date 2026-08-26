/* SoAI - Settings feature MCP service [frontend/assets/ts/features/settings/mcp/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { settleSettingsCapability } from '@features/settings/capabilityAvailability.ts';
import type { McpManagerDataHost, McpManagerDataRefresh } from '@features/settings/mcp/contracts.ts';

const fetchMcpManagerData = async (page: McpManagerDataHost): Promise<McpManagerDataRefresh> => {
    const api = page.services.api.mcp;
    const [status, servers, connections, search, rootsResponse, interactions, tools, resources, prompts] = await Promise.all([settleSettingsCapability(() => api.status()), settleSettingsCapability(() => api.servers.list()), settleSettingsCapability(() => api.connections.list()), settleSettingsCapability(() => api.searchApiKeys.list()), settleSettingsCapability(() => api.roots.get()), settleSettingsCapability(() => api.interactions.list()), settleSettingsCapability(() => api.tools.list()), settleSettingsCapability(() => api.resources.list()), settleSettingsCapability(() => api.prompts.list())]);
    return {
        status,
        servers,
        connections,
        search: search.succeeded && search.value ? { succeeded: true, value: { keys: search.value.keys, providers: search.value.providers }, error: null } : { succeeded: false, value: null, error: search.error },
        roots: rootsResponse.succeeded && rootsResponse.value ? { succeeded: true, value: rootsResponse.value.roots, error: null } : { succeeded: false, value: null, error: rootsResponse.error },
        interactions,
        tools,
        resources,
        prompts
    };
};

const applyMcpManagerData = (page: McpManagerDataHost, refresh: McpManagerDataRefresh): void => {
    if (refresh.status.succeeded) page.data.setMcpStatus(refresh.status.value);
    if (refresh.servers.succeeded && refresh.servers.value) page.data.setMcpServers(refresh.servers.value);
    if (refresh.connections.succeeded && refresh.connections.value) page.data.setMcpConnections(refresh.connections.value);
    if (refresh.search.succeeded && refresh.search.value) {
        page.data.setMcpSearchKeys(refresh.search.value.keys);
        page.data.setMcpSearchProviders(refresh.search.value.providers);
    }
    if (refresh.roots.succeeded && refresh.roots.value) page.data.setMcpRoots(refresh.roots.value);
    if (refresh.interactions.succeeded && refresh.interactions.value) page.data.setMcpInteractions(refresh.interactions.value);
    if (refresh.tools.succeeded && refresh.tools.value) page.data.setMcpTools(refresh.tools.value);
    if (refresh.resources.succeeded && refresh.resources.value) page.data.setMcpResources(refresh.resources.value);
    if (refresh.prompts.succeeded && refresh.prompts.value) page.data.setMcpPrompts(refresh.prompts.value);
};

const collectMcpManagerFailures = (refresh: McpManagerDataRefresh): Error[] => {
    const failures: Error[] = [];
    const results = [refresh.status, refresh.servers, refresh.connections, refresh.search, refresh.roots, refresh.interactions, refresh.tools, refresh.resources, refresh.prompts];
    for (const result of results) {
        if (!result.succeeded && result.error) {
            failures.push(result.error);
        }
    }
    return failures;
};

const countMcpManagerSuccesses = (refresh: McpManagerDataRefresh): number => {
    return [refresh.status, refresh.servers, refresh.connections, refresh.search, refresh.roots, refresh.interactions, refresh.tools, refresh.resources, refresh.prompts].filter((result) => result.succeeded).length;
};

export { applyMcpManagerData, collectMcpManagerFailures, countMcpManagerSuccesses, fetchMcpManagerData };

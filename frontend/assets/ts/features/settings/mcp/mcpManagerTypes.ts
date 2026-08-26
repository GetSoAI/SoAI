/* SoAI - Settings feature MCP manager types [frontend/assets/ts/features/settings/mcp/mcpManagerTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { JsonValue, JsonObject } from '@core/types/jsonValues.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import type { PageSanitizer, SettingsPageApi } from '@features/settings/contracts/contracts.ts';
import type { McpConnection, McpInteractionEntry, McpPromptEntry, McpResourceEntry, McpRootEntry, McpSearchKeyEntry, McpServer, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import type { McpServerAuthType, McpServerTransportType } from '@core/mcp/serverValues.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface McpManagerDependencies {
    host: McpManagerHost;
}

interface McpServerFormData {
    name: string;
    transportType: McpServerTransportType;
    endpoint: string;
    authType: McpServerAuthType;
    timeoutMs: number | null;
    autoReconnect: boolean;
    enabled: boolean;
    inputArguments: string[] | null;
    env: Record<string, string> | null;
    headers: Record<string, string> | null;
    apiKey: string | null;
    oauthClientId: string | null;
    oauthClientSecret: string | null;
}

interface McpManagerServicesHost {
    api: SettingsPageApi;
    isAdmin: () => boolean;
    getCurrentUserId: () => number;
    hasSearchQuery: () => boolean;
    createDebouncedHandler: <TArguments extends JsonValue[]>(handler: (...inputArguments: TArguments) => void, debounceTime?: number) => ((...inputArguments: TArguments) => void) & { cancel: () => void };
    pageContext: { sanitizer: PageSanitizer };
    dom: { getData: (element: Element, key: string) => string | null };
    filterSettings: () => void;
}

interface McpManagerDomHost extends PageDomOwnerHost, PageResourcesOwnerHost {
    updatePreferenceToggleLabel: (element: Element, checked?: boolean) => void;
    updateProperty: (element: Element, property: string, value: DomPropertyValue) => void;
    warnAndFocus: (element: Element | null, message: string) => void;
}

interface McpManagerExecutionHost extends PageFeedbackOwnerHost {
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
    withButtonDisabled: <T>(btn: Element | null, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: <Result>(boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null) => Promise<void>;
    notifySaveChanged: () => void;
    requestSave: () => void;
    syncManualDirtyField: (key: string, modified: boolean, valid: boolean) => void;
    clearManualDirtyField: (key: string) => void;
}

interface McpManagerDataHost {
    canPatchCoreConfig: () => boolean;
    getCoreConfig: () => JsonObject;
    getMcpData: () => {
        status: McpStatus | null;
        servers: McpServer[];
        connections: McpConnection[];
        searchKeys: McpSearchKeyEntry[];
        searchProviders: string[];
        roots: McpRootEntry[];
        interactions: McpInteractionEntry[];
        tools: McpToolEntry[];
        resources: McpResourceEntry[];
        prompts: McpPromptEntry[];
    };
    setMcpStatus: (status: McpStatus | null) => void;
    setMcpServers: (servers: McpServer[]) => void;
    setMcpConnections: (connections: McpConnection[]) => void;
    setMcpSearchKeys: (keys: McpSearchKeyEntry[]) => void;
    setMcpSearchProviders: (providers: string[]) => void;
    setMcpRoots: (roots: McpRootEntry[]) => void;
    setMcpInteractions: (interactions: McpInteractionEntry[]) => void;
    setMcpTools: (tools: McpToolEntry[]) => void;
    setMcpResources: (resources: McpResourceEntry[]) => void;
    setMcpPrompts: (prompts: McpPromptEntry[]) => void;
}

interface McpManagerEditStateHost {
    getMcpServerEditId: () => string | null;
    setMcpServerEditId: (id: string | null) => void;
    getMcpServerEditBaseline: () => McpServer | null;
    setMcpServerEditBaseline: (server: McpServer | null) => void;
    getMcpRootEditIndex: () => number | null;
    setMcpRootEditIndex: (index: number | null) => void;
    rebindConfigForm: () => void;
}

interface McpManagerHost {
    services: McpManagerServicesHost;
    view: McpManagerDomHost;
    execution: McpManagerExecutionHost;
    data: McpManagerDataHost;
    editing: McpManagerEditStateHost;
}

export type { McpManagerDependencies, McpManagerHost, McpServerFormData };

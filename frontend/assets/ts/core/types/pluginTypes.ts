/* SoAI - Plugin domain type declarations [frontend/assets/ts/core/types/pluginTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

import type { Plugin, PluginCapabilities } from '@core/types/catalogPluginTypes.ts';

export interface PluginStats {
    backendVariantAvailableCount?: number;
    modelCount?: number;
    providerCount?: number;
}

export interface PluginTechnical {
    filePath?: string;
    fileHash?: string;
    maxConcurrentRequests?: number;
    firstSeenAtMs?: number;
    lastSeenAtMs?: number;
}

export interface PluginModelRepositoryCatalogEntry extends JsonObject {
    id?: string;
    name?: string;
    slug?: string;
    displayName?: string;
    repositoryUrl?: string;
    aliases?: JsonValue[];
    tags?: JsonValue[];
}

export interface PluginModelRepositoryRecord extends JsonObject {
    catalog?: PluginModelRepositoryCatalogEntry[];
    repositoryUrl?: string;
    url?: string;
    baseUrl?: string;
    link?: string;
    href?: string;
    displayName?: string;
    name?: string;
    tags?: JsonValue[];
}

export type PluginModelRepository = string | PluginModelRepositoryRecord | null;

export interface OpenAICapabilities extends JsonObject {
    modalities?: string[];
}

export interface PluginCapabilitiesExtended extends PluginCapabilities {
    hasConfiguration?: boolean;
    supportsCloning?: boolean;
    supportsBackendInstallation?: boolean;
    supportsModelDownload?: boolean;
    externalProviderMode?: string;
    openai?: OpenAICapabilities | null;
}

export interface PluginRecord extends Omit<Plugin, 'capabilities'> {
    id?: string;
    logo?: string;
    icon?: string;
    logoRevision?: string | null;
    backendVersion?: string;
    disabledReason?: string | null;
    modalities?: string[];
    icons?: { default?: string };
    assets?: { logo?: string };
    metadata?: { logo?: string };
    stats?: PluginStats;
    modelTypes?: JsonValue[];
    modelRepository?: PluginModelRepository;
    externalProviderDefaults?: JsonValue;
    technical?: PluginTechnical;
    context?: JsonValue;
    capabilities?: PluginCapabilitiesExtended;
    descriptionSoaiplugin?: string;
    authorSoaiplugin?: string;
    versionSoaiplugin?: string;
    licenseSoaiplugin?: string;
    licenseManagedBackend?: string | null;
    websiteSoaiplugin?: string;
    websiteBackend?: string;
    coreCompat?: string;
}

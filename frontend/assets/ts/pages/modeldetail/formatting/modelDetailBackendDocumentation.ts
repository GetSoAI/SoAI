/* SoAI - Model detail page formatting backend documentation [frontend/assets/ts/pages/modeldetail/formatting/modelDetailBackendDocumentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation } from '@core/environment/public.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { resolveHttpUrl } from '@core/security/public.ts';
import { hasOwn, isArray, isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

interface ResolveBackendDocumentationOptions {
    ensurePlugins?: boolean;
    plugins?: (JsonValue | null)[] | null;
}

interface ModelDetailBackendDocumentationHost {
    model: ModelRecord | null;
    pluginCollectionSnapshot: (JsonValue | null)[];
    getResource(resource: string, options?: JsonObject): JsonValue | ResourceSnapshot | null;
}

interface ModelDetailBackendDocumentationResult {
    url: string | null;
    pluginCollectionSnapshot: (JsonValue | null)[];
}

const normalizeDocumentationUrl = (url: JsonValue | null | undefined): string | null => {
    if (!isString(url) || !url.trim()) return null;
    return resolveHttpUrl(url, getLocation().origin);
};

const resolveModelDetailBackendDocumentation = (host: ModelDetailBackendDocumentationHost, { ensurePlugins = true, plugins = null }: ResolveBackendDocumentationOptions = {}): ModelDetailBackendDocumentationResult => {
    let resolvedUrl: string | null = null;
    let pluginSnapshot = host.pluginCollectionSnapshot;
    const model = host.model;
    if (model) {
        [model.websiteBackend, model.backendDocumentation].some((candidate: JsonValue | null | undefined) => {
            const normalized = normalizeDocumentationUrl(candidate);
            if (normalized) {
                resolvedUrl = normalized;
                return true;
            }
            return false;
        });
        if (!resolvedUrl) {
            const pluginName = model.plugin || model.provider;
            if (pluginName) {
                let list: (JsonValue | null)[] = isArray(plugins) ? plugins : pluginSnapshot;
                if ((!list || !list.length) && ensurePlugins) {
                    const resource = host.getResource(PLUGINS, { state: true });
                    const resourceValue = isObject(resource) && hasOwn(resource, 'value') ? resource['value'] : null;
                    if (isArray(resourceValue)) {
                        list = Array.from(resourceValue);
                        pluginSnapshot = list;
                    }
                }
                if (isArray(list)) {
                    const pluginKey = String(pluginName).toLowerCase();
                    const match = list.find((entry: JsonValue | null) => {
                        if (!isObject(entry)) {
                            return false;
                        }
                        const name = entry['name'];
                        return isString(name) && name.toLowerCase() === pluginKey;
                    });
                    if (match && isObject(match)) {
                        [match['websiteBackend']].some((candidate: JsonValue | null | undefined) => {
                            const normalized = normalizeDocumentationUrl(candidate);
                            if (normalized) {
                                resolvedUrl = normalized;
                                return true;
                            }
                            return false;
                        });
                    }
                }
            }
        }
    }
    return {
        url: resolvedUrl,
        pluginCollectionSnapshot: pluginSnapshot
    };
};

export { resolveModelDetailBackendDocumentation };
export type { ModelDetailBackendDocumentationHost, ModelDetailBackendDocumentationResult, ResolveBackendDocumentationOptions };

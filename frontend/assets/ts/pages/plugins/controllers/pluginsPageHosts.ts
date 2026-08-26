/* SoAI - Plugins page control layer host composition [frontend/assets/ts/pages/plugins/controllers/pluginsPageHosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CardRendererHost } from '@core/ui/BaseCardRenderer.ts';
import type { PluginCardHost } from '@pages/plugins/rendering/cardrenderer/types.ts';

interface PluginsPageCardHostDependencies {
    createFragment: (markup: TrustedHtml) => DocumentFragment;
    sanitizeClassName: CardRendererHost['sanitizeClassName'];
    status: PluginCardHost['status'];
    compatibility: PluginCardHost['compatibility'];
    presentation: PluginCardHost['presentation'];
    actions: Omit<PluginCardHost['actions'], 'getItemCardId'> & { getItemCardId(plugin: PluginRecord): JsonValue };
}

function buildPluginsPageCardHost(dependencies: PluginsPageCardHostDependencies): PluginCardHost {
    return {
        dom: { createFragment: dependencies.createFragment },
        sanitizeClassName: dependencies.sanitizeClassName,
        status: dependencies.status,
        compatibility: dependencies.compatibility,
        presentation: dependencies.presentation,
        actions: {
            ...dependencies.actions,
            getItemCardId: (plugin: PluginRecord): string | null => {
                const id = dependencies.actions.getItemCardId(plugin);
                if (id === null || id === undefined) return null;
                const normalized = String(id).trim();
                return normalized ? normalized : null;
            }
        }
    };
}

export { buildPluginsPageCardHost };

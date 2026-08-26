/* SoAI - MCP pending save coordinator [frontend/assets/ts/features/settings/mcp/mcpSaveCoordinatorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpRootsManager } from '@features/settings/mcp/mcpRoots.ts';
import type { McpSearchKeysManager } from '@features/settings/mcp/mcpSearchKeys.ts';
import type { McpServersManager } from '@features/settings/mcp/mcpServers.ts';

interface McpSaveCoordinator {
    hasChanges: () => boolean;
    arePendingChangesValid: () => boolean;
    savePendingChanges: () => Promise<void>;
}

const createMcpSaveCoordinator = (dependencies: { servers: McpServersManager; roots: McpRootsManager; searchKeys: McpSearchKeysManager; reload: () => Promise<boolean> }): McpSaveCoordinator => {
    const computeDirtyState = (): { servers: boolean; roots: boolean; searchKeys: boolean } => ({
        servers: dependencies.servers.hasPendingChanges(),
        roots: dependencies.roots.hasPendingChanges(),
        searchKeys: dependencies.searchKeys.hasPendingChanges()
    });

    return {
        hasChanges: (): boolean => {
            const dirty = computeDirtyState();
            return dirty.servers || dirty.roots || dirty.searchKeys;
        },
        arePendingChangesValid: (): boolean => {
            const dirty = computeDirtyState();
            if (dirty.servers && !dependencies.servers.isPendingChangesValid()) {
                return false;
            }
            if (dirty.searchKeys && !dependencies.searchKeys.isPendingChangesValid()) {
                return false;
            }
            if (dirty.roots && !dependencies.roots.isPendingChangesValid()) {
                return false;
            }
            return true;
        },
        savePendingChanges: async (): Promise<void> => {
            const dirty = computeDirtyState();
            if (dirty.servers && !dependencies.servers.validatePendingChanges()) {
                return;
            }
            if (dirty.searchKeys && !dependencies.searchKeys.validatePendingChanges()) {
                return;
            }
            if (dirty.roots && !dependencies.roots.validatePendingChanges()) {
                return;
            }
            let shouldReload = false;
            if (dirty.servers) {
                const changed = await dependencies.servers.saveServer({ reloadAfterSave: false });
                shouldReload = shouldReload || changed;
            }
            if (dirty.searchKeys) {
                const changed = await dependencies.searchKeys.saveSearchKey({ reloadAfterSave: false });
                shouldReload = shouldReload || changed;
            }
            if (dirty.roots) {
                const changed = await dependencies.roots.saveRoot({ reloadAfterSave: false });
                shouldReload = shouldReload || changed;
            }
            if (shouldReload) {
                await dependencies.reload();
            }
        }
    };
};

export { createMcpSaveCoordinator };
export type { McpSaveCoordinator };

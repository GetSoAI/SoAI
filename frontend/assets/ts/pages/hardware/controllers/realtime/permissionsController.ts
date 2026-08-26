/* SoAI - Hardware page permissions controller [frontend/assets/ts/pages/hardware/controllers/realtime/permissionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

interface HardwarePermissionsLoadDependencies {
    state: HardwarePageState;
    logger: ModuleLoggerFunctionValue;
    applyPermissionGates(): void;
}

interface HardwarePermissionsSnapshotDependencies {
    state: HardwarePageState;
    logger: ModuleLoggerFunctionValue;
}

const ensureHardwareWebuiPermissions = async (dependencies: HardwarePermissionsSnapshotDependencies): Promise<void> => {
    if (dependencies.state.webuiPermissions) {
        return;
    }
    try {
        const permissions = await loadWebuiPermissionsSnapshot();
        dependencies.state.webuiPermissions = { actions: [...permissions.actions], isAdmin: permissions.isAdmin };
    } catch (error) {
        const runtimeError = ensureError(error);
        dependencies.logger('warn', 'Failed to load webui.permissions snapshot', runtimeError);
        throw runtimeError;
    }
};

const loadHardwareWebuiPermissions = async (dependencies: HardwarePermissionsLoadDependencies): Promise<void> => {
    await ensureHardwareWebuiPermissions(dependencies);
    dependencies.applyPermissionGates();
};

export { ensureHardwareWebuiPermissions, loadHardwareWebuiPermissions };

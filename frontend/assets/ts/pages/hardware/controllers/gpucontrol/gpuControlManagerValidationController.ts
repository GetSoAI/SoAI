/* SoAI - Hardware page GPU control manager validation controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlManagerValidationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import type { GpuControlManagerDependencies, SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const validateGpuControlManagerDependencies = (dependencies: GpuControlManagerDependencies, security: SecurityService | undefined): SecurityService => {
    if (!dependencies?.pageDom || !isFunction(dependencies.pageDom.resolveContext)) {
        throw new Error('GpuControlManager requires a page DOM owner with resolveContext()');
    }
    if (!isFunction(dependencies.getIconSync)) {
        throw new Error('GpuControlManager requires getIconSync()');
    }
    if (!security || !isFunction(security.escapeHtml) || !isFunction(security.escapeAttribute)) {
        throw new Error('GpuControlManager requires a SecurityService');
    }
    return security;
};

export { validateGpuControlManagerDependencies };

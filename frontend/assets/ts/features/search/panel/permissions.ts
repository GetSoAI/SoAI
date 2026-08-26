/* SoAI - Frontend search ACL permission loading [frontend/assets/ts/features/search/panel/permissions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const loadSearchGrantedActions = async (): Promise<ReadonlySet<string>> => {
    try {
        return (await loadWebuiPermissionsSnapshot()).grantedActions;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('SearchPanel', 'Failed to load webui.permissions snapshot', runtimeError);
        return new Set();
    }
};

export { loadSearchGrantedActions };

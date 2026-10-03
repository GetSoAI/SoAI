/* SoAI - Frontend search ACL permission loading [frontend/assets/ts/features/search/panel/permissions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { WebuiPermissionsUnavailableError } from '@core/access/permissionFailure.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface SearchPermissionState {
    grantedActions: ReadonlySet<string>;
    permissionError: Error | null;
    invalidateSearches(): void;
}

class SearchPermissions {
    readonly #requests = new LatestRequestController();

    cancel(): void {
        this.#requests.invalidate();
    }

    async refresh(state: SearchPermissionState, onAccessChanged: () => void): Promise<boolean> {
        return (
            (await this.#requests.runLatest(async (request) => {
                state.permissionError = null;
                state.grantedActions = new Set();
                state.invalidateSearches();
                onAccessChanged();
                try {
                    const snapshot = await loadWebuiPermissionsSnapshot({ signal: request.signal });
                    if (request.isStale()) return false;
                    state.grantedActions = snapshot.grantedActions;
                    state.invalidateSearches();
                    onAccessChanged();
                    return true;
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (request.isStale() || isAbortError(runtimeError)) return false;
                    state.permissionError = runtimeError instanceof WebuiPermissionsUnavailableError ? runtimeError : new WebuiPermissionsUnavailableError(runtimeError);
                    errorHandler.warn('SearchPanel', 'Permissions unavailable', runtimeError);
                    return false;
                }
            })) ?? false
        );
    }
}

export { SearchPermissions };

/* SoAI - WebUI permission snapshot loading [frontend/assets/ts/core/access/webuiPermissions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WebuiPermissionsUnavailableError } from '@core/access/permissionFailure.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { uniqueSortedStrings } from '@core/normalize.ts';
import { isBoolean } from '@core/typeGuards.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import type { SnapshotRequestOptions } from '@core/websocketclient/types.ts';

interface WebuiPermissionsSnapshot {
    readonly actions: readonly string[];
    readonly grantedActions: ReadonlySet<string>;
    readonly isAdmin: boolean;
}

const loadWebuiPermissionsSnapshot = async (options: SnapshotRequestOptions = {}): Promise<WebuiPermissionsSnapshot> => {
    const payload = await requestWebSocketSnapshotRecord('webui.permissions', null, { retryOnReconnect: true, ...options }).catch((error) => {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError) || isLifecycleCancellationError(runtimeError)) throw runtimeError;
        throw new WebuiPermissionsUnavailableError(runtimeError);
    });
    if (!isBoolean(payload['is_admin'])) {
        throw new Error('webui.permissions.is_admin must be a boolean');
    }
    const actions = uniqueSortedStrings(readRequiredTrimmedStringArrayValue(payload['actions'], 'webui.permissions.actions'), 'en');
    return {
        actions,
        grantedActions: new Set(actions),
        isAdmin: payload['is_admin']
    };
};

const hasWebuiAction = async (action: string): Promise<boolean> => (await loadWebuiPermissionsSnapshot()).grantedActions.has(action);

export { hasWebuiAction, loadWebuiPermissionsSnapshot };
export type { WebuiPermissionsSnapshot };

/* SoAI - WebUI permission snapshot loading [frontend/assets/ts/core/access/webuiPermissions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
    const payload = await requestWebSocketSnapshotRecord('webui.permissions', null, options);
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

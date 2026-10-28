/* SoAI - Restricted setup status event validation [frontend/assets/ts/core/realtime/eventcontracts/setupStatusContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface SetupStatusSnapshot {
    setupNeeded: boolean;
    hasUsers: boolean;
}

const decodeSetupStatusEvent = (value: JsonValue): SetupStatusSnapshot => {
    const envelope = requireRecord(value, 'Setup status event');
    assertExactRecordKeys(envelope, ['type', 'data'], 'Setup status event');
    if (envelope['type'] !== 'setup_status') throw new TypeError('Setup status event type is invalid');
    const data = requireRecord(envelope['data'], 'Setup status data');
    assertExactRecordKeys(data, ['setup_needed', 'has_users'], 'Setup status data');
    const setupNeeded = data['setup_needed'];
    const hasUsers = data['has_users'];
    if (typeof setupNeeded !== 'boolean' || typeof hasUsers !== 'boolean' || setupNeeded === hasUsers) throw new TypeError('Setup status state is inconsistent');
    return { setupNeeded, hasUsers };
};

export { decodeSetupStatusEvent };
export type { SetupStatusSnapshot };

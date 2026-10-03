/* SoAI - SoAI Connect pairing details boundary contract [frontend/assets/ts/core/api/contracts/systemConnectPairingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readRequiredFiniteIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

type ConnectPairingScheme = 'http' | 'https';
type ConnectPairingBindScope = 'loopback' | 'all_interfaces' | 'specific';

interface ConnectPairingResponse {
    readonly scheme: ConnectPairingScheme;
    readonly port: number;
    readonly instanceId: string;
    readonly bindScope: ConnectPairingBindScope;
    readonly addresses: readonly string[];
}

const CANONICAL_UUID4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const LABEL = 'Connect pairing response';

const decodeConnectPairing = (value: ApiResponsePayload): ConnectPairingResponse => {
    const record = requireRecord(value, LABEL);
    assertExactRecordKeys(record, ['scheme', 'port', 'instance_id', 'bind_scope', 'addresses'], LABEL);
    const port = readRequiredFiniteIntegerValue(record['port'], `${LABEL}.port`);
    if (port < 1 || port > 65535) throw new TypeError(`${LABEL}.port must be from 1 through 65535`);
    const instanceId = readRequiredTrimmedStringValue(record['instance_id'], `${LABEL}.instance_id`);
    if (!CANONICAL_UUID4_PATTERN.test(instanceId)) throw new TypeError(`${LABEL}.instance_id must be a canonical UUID4`);
    return {
        scheme: readRequiredEnumValue(record['scheme'], `${LABEL}.scheme`, ['http', 'https']),
        port,
        instanceId,
        bindScope: readRequiredEnumValue(record['bind_scope'], `${LABEL}.bind_scope`, ['loopback', 'all_interfaces', 'specific']),
        addresses: readRequiredTrimmedStringArrayValue(record['addresses'], `${LABEL}.addresses`)
    };
};

export { decodeConnectPairing };
export type { ConnectPairingBindScope, ConnectPairingResponse, ConnectPairingScheme };

/* SoAI - Licensing runtime state contract [frontend/assets/ts/core/licensing/licensingState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type LicensingState = 'personal_declared' | 'evaluation_pending' | 'evaluation_active' | 'evaluation_expiring' | 'evaluation_expired' | 'personal_os_perpetual_active' | 'commercial_active' | 'commercial_expiring' | 'commercial_continuity' | 'commercial_expired' | 'commercial_perpetual_active' | 'suspended' | 'terminated' | 'invalid_signature' | 'invalid_binding' | 'invalid_contract' | 'clock_invalid';

const LICENSING_REPAIR_STATES: ReadonlySet<LicensingState> = new Set(['evaluation_expired', 'commercial_expired', 'suspended', 'terminated', 'invalid_signature', 'invalid_binding', 'invalid_contract', 'clock_invalid']);
const LICENSING_ATTENTION_STATES: ReadonlySet<LicensingState> = new Set(['evaluation_pending', 'evaluation_expiring', 'commercial_expiring', 'commercial_continuity']);

const requireLicensingState = (value: JsonValue | undefined, label: string = 'Licensing state'): LicensingState => {
    switch (value) {
        case 'personal_declared':
        case 'evaluation_pending':
        case 'evaluation_active':
        case 'evaluation_expiring':
        case 'evaluation_expired':
        case 'commercial_active':
        case 'commercial_expiring':
        case 'commercial_continuity':
        case 'commercial_expired':
        case 'suspended':
        case 'terminated':
        case 'invalid_signature':
        case 'invalid_binding':
        case 'invalid_contract':
        case 'clock_invalid':
        case 'personal_os_perpetual_active':
        case 'commercial_perpetual_active':
            return value;
        default:
            throw new TypeError(`${label} is invalid.`);
    }
};

const licensingStateRequiresRepair = (state: LicensingState): boolean => LICENSING_REPAIR_STATES.has(state);
const licensingStateNeedsAttention = (state: LicensingState): boolean => LICENSING_ATTENTION_STATES.has(state);

export { licensingStateNeedsAttention, licensingStateRequiresRepair, requireLicensingState };
export type { LicensingState };

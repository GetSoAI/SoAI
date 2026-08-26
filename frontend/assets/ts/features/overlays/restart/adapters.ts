/* SoAI - Overlays feature adapters [frontend/assets/ts/features/overlays/restart/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isApiInterface, isDomInterface } from '@features/overlays/restart/guards.ts';
import type { ApiInterface, DomInterface } from '@features/overlays/restart/types.ts';

type RestartServiceCandidate = ApiInterface | DomInterface | JsonValue | SoAIRegisteredService | null;

const resolveRestartApi = (current: ApiInterface | null, resolveService: (name: string) => RestartServiceCandidate): ApiInterface => {
    if (current) {
        return current;
    }
    const candidate = resolveService('core.apiClient');
    if (!isApiInterface(candidate)) {
        throw new Error('core.apiClient does not satisfy RestartOverlay API requirements');
    }
    return candidate;
};

const resolveRestartDom = (current: DomInterface | null, resolveService: (name: string) => RestartServiceCandidate): DomInterface => {
    if (current) {
        return current;
    }
    const candidate = resolveService('core.dom');
    if (!isDomInterface(candidate)) {
        throw new Error('core.dom does not satisfy RestartOverlay DOM requirements');
    }
    return candidate;
};

export { resolveRestartApi, resolveRestartDom };

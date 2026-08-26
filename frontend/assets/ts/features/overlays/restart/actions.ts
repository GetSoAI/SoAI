/* SoAI - Overlays feature restart actions [frontend/assets/ts/features/overlays/restart/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import type { LocationInterface } from '@features/overlays/restart/types.ts';

const reloadCurrentLocation = (getLocationFunctionValue: () => LocationInterface): void => {
    const locationRef = getLocationFunctionValue();
    if (!isFunction(locationRef.reload)) {
        throw new Error('Location.reload must be available for restart overlay');
    }
    locationRef.reload();
};

export { reloadCurrentLocation };

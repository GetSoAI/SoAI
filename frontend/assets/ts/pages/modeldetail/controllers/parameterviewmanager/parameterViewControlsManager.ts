/* SoAI - Parameter view control management [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/parameterViewControlsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { ParameterGroup } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { FILTER_ALL_VALUE, FILTER_GROUP_PREFIX, isParameterGroup } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';

const readModelDetailParameterGroup = (storage: PageControlsStorageInput): ParameterGroup | null => {
    const stored = requirePageControlsStorage(storage).getPageControlState('modelDetail').parameterFilter;
    const group = stored?.startsWith(FILTER_GROUP_PREFIX) ? stored.substring(FILTER_GROUP_PREFIX.length) : null;
    return isParameterGroup(group) ? group : null;
};

const persistModelDetailParameterGroup = (storage: PageControlsStorageInput, group: ParameterGroup | null): void => {
    requirePageControlsStorage(storage).setPageControlState('modelDetail', {
        parameterFilter: group ? `${FILTER_GROUP_PREFIX}${group}` : FILTER_ALL_VALUE
    });
};

export { persistModelDetailParameterGroup, readModelDetailParameterGroup };

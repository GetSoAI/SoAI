/* SoAI - Parameter view control management [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/parameterViewControlsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import { FILTER_ALL_VALUE } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';

const readModelDetailParameterFilter = (storage: PageControlsStorageInput): string => {
    const state = requirePageControlsStorage(storage).getPageControlState('modelDetail');
    return state.parameterFilter || FILTER_ALL_VALUE;
};

const persistModelDetailParameterFilter = (storage: PageControlsStorageInput, parameterFilter: string): void => {
    requirePageControlsStorage(storage).setPageControlState('modelDetail', {
        parameterFilter: parameterFilter || FILTER_ALL_VALUE
    });
};

export { persistModelDetailParameterFilter, readModelDetailParameterFilter };

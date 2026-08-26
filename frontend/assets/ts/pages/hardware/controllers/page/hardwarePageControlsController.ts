/* SoAI - Hardware page controls controller [frontend/assets/ts/pages/hardware/controllers/page/hardwarePageControlsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { requirePageControlsStorage, type PageControlsStorage } from '@core/pagecontrols/storageController.ts';
import type { HardwarePageControlState } from '@core/storage/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { normalizeStoredSortState } from '@core/ui/tables/sortableTable.ts';
import { STR_CPU, STR_USAGE } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import type { HardwareLayoutStorage } from '@pages/hardware/controllers/page/hardwareLayoutController.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import { PROCESS_SORT_COLUMNS, PROCESS_SORT_DEFAULT_DIRECTIONS } from '@pages/hardware/widgets/processes/ProcessSortDefinitionsWidget.ts';
import type { ProcessSortColumn, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

interface HardwareProcessSortState {
    column: ProcessSortColumn;
    direction: SortDirection;
}

const positiveIntegerOrFallback = (value: JsonValue, fallback: number): number => {
    return typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.round(value) : fallback;
};

interface HardwarePageControlsStorageCandidate {
    getPageControlState: (pageId: 'hardware') => HardwarePageControlState;
    setPageControlState: (pageId: 'hardware', value: Partial<HardwarePageControlState>) => void;
}

type HardwarePageControlsStorage = HardwareLayoutStorage | HardwarePageControlsStorageCandidate | JsonValue | null | undefined;

const isHardwarePageControlsStorageCandidate = (storage: HardwarePageControlsStorage): storage is HardwarePageControlsStorageCandidate => {
    return isObject(storage) && 'getPageControlState' in storage && isFunction(storage.getPageControlState) && 'setPageControlState' in storage && isFunction(storage.setPageControlState);
};

const requireHardwarePageControlsStorage = (storage: HardwarePageControlsStorage): PageControlsStorage => {
    if (!isHardwarePageControlsStorageCandidate(storage)) {
        throw new Error('Hardware page controls require page control storage accessors');
    }
    return requirePageControlsStorage(storage);
};

const readHardwareProcessSortState = (storage: HardwarePageControlsStorage): HardwareProcessSortState => {
    const state = requireHardwarePageControlsStorage(storage).getPageControlState('hardware').processSort;
    return normalizeStoredSortState({ state, columns: PROCESS_SORT_COLUMNS, fallback: { column: 'cpu', direction: 'desc' }, defaultDirections: PROCESS_SORT_DEFAULT_DIRECTIONS });
};

const applyHardwarePageControls = (storage: HardwarePageControlsStorage, state: HardwarePageState): void => {
    const controls = requireHardwarePageControlsStorage(storage).getPageControlState('hardware');
    state.chartType = controls.chartType || 'area';
    state.selectedDevice = controls.category || STR_CPU;
    state.selectedMetric = controls.subcategory || STR_USAGE;
    state.timeRange = positiveIntegerOrFallback(controls.timeRange, 120);
    state.candlestickIntervalMinutes = positiveIntegerOrFallback(controls.candleInterval, 1);
};

const persistHardwarePageControls = (storage: HardwarePageControlsStorage, state: HardwarePageState, processSort: HardwareProcessSortState): void => {
    requireHardwarePageControlsStorage(storage).setPageControlState('hardware', {
        chartType: state.chartType || 'area',
        category: state.selectedDevice || STR_CPU,
        subcategory: state.selectedMetric || STR_USAGE,
        timeRange: state.timeRange,
        candleInterval: state.candlestickIntervalMinutes,
        processSort: {
            column: processSort.column,
            direction: processSort.direction
        }
    });
};

export { applyHardwarePageControls, persistHardwarePageControls, readHardwareProcessSortState };
export type { HardwareProcessSortState };

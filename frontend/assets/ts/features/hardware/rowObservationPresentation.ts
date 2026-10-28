/* SoAI - Hardware row observation presentation [frontend/assets/ts/features/hardware/rowObservationPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHardwareObservationFresh, shouldDimHardwareObservation, type HardwareComponentObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';

const syncHardwareRowObservationPresentation = (row: HTMLElement, observation: HardwareComponentObservation | undefined, monitoringIntervalMs?: number): void => {
    const count = isHardwareObservationFresh(observation) ? 0 : Number(row.dataset['staleCount'] ?? 0) + 1;
    row.dataset['staleCount'] = String(count);
    row.classList.toggle('hardware-observation-stale', shouldDimHardwareObservation(observation, count, serverEpochMs(), monitoringIntervalMs ?? 1000));
};

export { syncHardwareRowObservationPresentation };

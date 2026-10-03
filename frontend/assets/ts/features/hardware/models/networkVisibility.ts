/* SoAI - Hardware network interface visibility [frontend/assets/ts/features/hardware/models/networkVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WindowsNetworkInventoryStatus } from '@core/api/contracts/hardwareContracts.ts';
import type { HardwareSnapshot } from '@features/hardware/models/types.ts';

const getWindowsNetworkInventoryStatus = (snapshot: HardwareSnapshot | null | undefined): WindowsNetworkInventoryStatus | null => snapshot?.network?.windowsInventoryStatus ?? null;

const isVisibleNetworkInterfaceName = (name: string, windowsInventoryStatus: WindowsNetworkInventoryStatus | null, ignorePrefixes: readonly string[]): boolean => {
    if (windowsInventoryStatus === 'available') {
        return true;
    }
    if (windowsInventoryStatus === 'unavailable') {
        return false;
    }
    const normalizedName = name.trim().toLowerCase();
    return !ignorePrefixes.some((prefix) => normalizedName.startsWith(prefix.toLowerCase()));
};

export { getWindowsNetworkInventoryStatus, isVisibleNetworkInterfaceName };

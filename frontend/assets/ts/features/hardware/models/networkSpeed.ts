/* SoAI - Hardware feature network speed [frontend/assets/ts/features/hardware/models/networkSpeed.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NetworkSpeedEntry, NetworkSpeedSnapshot } from '@features/hardware/models/types.ts';

const resolveNetworkSpeedEntry = (speeds: NetworkSpeedSnapshot | null | undefined, interfaceName: string, deviceId: string): NetworkSpeedEntry | null => {
    if (!speeds) {
        return null;
    }
    const normalizedName = interfaceName.trim().toLowerCase();
    const normalizedDeviceId = deviceId.trim().toLowerCase();
    if (!normalizedName && !normalizedDeviceId) {
        return null;
    }
    for (const [key, entry] of Object.entries(speeds)) {
        const normalizedKey = key.trim().toLowerCase();
        if (normalizedKey === normalizedName || normalizedKey === normalizedDeviceId) {
            return entry;
        }
    }
    return null;
};

export { resolveNetworkSpeedEntry };

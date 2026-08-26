/* SoAI - Hardware feature device names [frontend/assets/ts/features/hardware/deviceNames.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';

interface HardwareNamedDevice {
    readonly displayName?: string | undefined;
    readonly name?: string | undefined;
}

const resolveHardwareDeviceDisplayName = (device: HardwareNamedDevice): string | null => toTrimmedStringOrNull(device.displayName) ?? toTrimmedStringOrNull(device.name);

export { resolveHardwareDeviceDisplayName };
export type { HardwareNamedDevice };

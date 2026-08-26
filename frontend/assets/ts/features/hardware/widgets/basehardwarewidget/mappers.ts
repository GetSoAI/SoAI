/* SoAI - Base hardware widget mapping [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DeviceNamePresentation, DeviceNamePresentationInput } from '@features/hardware/widgets/basehardwarewidget/types.ts';

const resolveDeviceNamePresentation = ({ parts, options }: DeviceNamePresentationInput): DeviceNamePresentation => {
    const threshold = options?.longNameThreshold ?? 30;
    const fullName = parts.secondary ? `${parts.primary} ${parts.secondary}` : parts.primary;
    const className = fullName.length > threshold ? 'hardware-widget__device-name hardware-widget__device-name--long' : 'hardware-widget__device-name';
    return {
        className,
        primary: parts.primary,
        secondary: parts.secondary
    };
};

export { resolveDeviceNamePresentation };

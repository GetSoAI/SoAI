/* SoAI - Base hardware widget contracts [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DeviceNameParts } from '@features/hardware/widgets/contracts.ts';

interface ChartPathValues {
    areaPath: string;
    linePath: string;
}

interface DeviceNamePresentation {
    className: string;
    primary: string;
    secondary: string | null;
}

interface DeviceNamePresentationOptions {
    longNameThreshold: number;
}

interface DeviceNamePresentationInput {
    parts: DeviceNameParts;
    options?: DeviceNamePresentationOptions;
}

export type { ChartPathValues, DeviceNamePresentation, DeviceNamePresentationInput, DeviceNamePresentationOptions };

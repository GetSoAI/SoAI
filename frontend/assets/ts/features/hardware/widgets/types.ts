/* SoAI - Hardware feature widgets public contracts [frontend/assets/ts/features/hardware/widgets/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WidgetSize } from '@features/hardware/widgets/constants.ts';

interface HardwareWidgetManagerOptions {
    container: HTMLElement;
    size?: WidgetSize | undefined;
}

export { type HardwareWidgetManagerOptions };

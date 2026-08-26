/* SoAI - Automation page time grid types [frontend/assets/ts/pages/automation/widgets/calendar/timeGridTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationColor } from '@features/automation/public.ts';
import type { AutomationZoneStatus } from '@pages/automation/types.ts';

interface TimeGridZoneLayout {
    key: string;
    title: string;
    startUtcMs: number;
    topPx: number;
    heightPx: number;
    leftPct: number;
    widthPct: number;
    isSelected: boolean;
    status: AutomationZoneStatus;
    color: AutomationColor;
}

export type { TimeGridZoneLayout };

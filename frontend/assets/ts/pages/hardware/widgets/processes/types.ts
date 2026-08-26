/* SoAI - Hardware page processes contracts [frontend/assets/ts/pages/hardware/widgets/processes/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import type { HardwareProcessRecord } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';

type ProcessRecord = HardwareProcessRecord;

type ProcessDisplayRow = {
    name: string;
    pid: number;
    cpu: number;
    mem: number;
    swap: number;
    swapKnown: boolean;
    user: string;
    time: number;
};

type ProcessSortColumn = 'name' | 'pid' | 'cpu' | 'memory' | 'runtime';

type ProcessSnapshot = {
    capabilities?: { platform?: string | null } | null;
};

type ProcessKillRequestOptions = {
    signal: number;
    useSudo: boolean;
    throwOnError?: boolean;
    notifyOnError?: boolean;
};

type ProcessKillResult = { status: string } | null;

type ProcessKillResolution = {
    message: string;
    type: string;
    retryElevated?: boolean;
};

type ProcessTableManagerDependencies = {
    optionalHTMLElement: (selector: string, parent?: Element | null) => HTMLElement | null;
    updateText: (element: Element, text: string) => void;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    runWithBoundary: (boundaryKey: string, functionValue: () => Promise<void>) => Promise<void>;
    showNotification: (message: string, type: string, duration?: number) => void;
    killProcess: (pid: string, options: ProcessKillRequestOptions) => Promise<ProcessKillResult>;
    getLastSnapshot: () => ProcessSnapshot | null;
    onSortChanged: (state: { column: ProcessSortColumn; direction: SortDirection }) => void;
};

export type { ProcessDisplayRow, ProcessKillRequestOptions, ProcessKillResolution, ProcessRecord, ProcessSortColumn, ProcessTableManagerDependencies, ProcessKillResult, ProcessSnapshot, SortDirection };

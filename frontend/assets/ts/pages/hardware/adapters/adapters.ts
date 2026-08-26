/* SoAI - Hardware page adapters implementation [frontend/assets/ts/pages/hardware/adapters/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { readNullableJsonObjectValue } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { createHardwareProcessTableDependencies } from '@pages/hardware/controllers/hardwareControllerFactories.ts';
import { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';
import type { ProcessTableManagerDependencies } from '@pages/hardware/widgets/processes/types.ts';

interface CreateHardwareProcessControllerDependencies {
    optionalHTMLElement(selector: string, parent?: Element | null): HTMLElement | null;
    updateText(element: Element, text: string): void;
    getIconSync(iconName: IconName, options?: IconOptions): TrustedHtml;
    runWithBoundary(boundaryKey: string, functionValue: () => Promise<void>): Promise<void>;
    showNotification(message: string, type: string, duration?: number): void;
    killProcess(pid: string, options: { signal: number; useSudo: boolean; throwOnError?: boolean; notifyOnError?: boolean }): Promise<JsonValue>;
    getLastSnapshot(): HardwarePageSnapshot | null;
    onSortChanged: ProcessTableManagerDependencies['onSortChanged'];
}

const createHardwareProcessController = (dependencies: CreateHardwareProcessControllerDependencies): ProcessTableManager => {
    const processTableDependencies = createHardwareProcessTableDependencies({
        optionalHTMLElement: (selector: string, parent?: Element | null) => dependencies.optionalHTMLElement(selector, parent),
        updateText: (element: Element, text: string) => dependencies.updateText(element, text),
        getIconSync: (iconName, options) => dependencies.getIconSync(iconName, options),
        runWithBoundary: (boundaryKey: string, functionValue: () => Promise<void>) => dependencies.runWithBoundary(boundaryKey, functionValue),
        showNotification: (message: string, type: string, duration?: number) => dependencies.showNotification(message, type, duration),
        killProcess: (pid: string, options: { signal: number; useSudo: boolean; throwOnError?: boolean; notifyOnError?: boolean }) =>
            dependencies.killProcess(pid, options).then((value) => {
                const response = readNullableJsonObjectValue(value, 'Kill process response');
                if (response === null) {
                    return null;
                }
                const status = readRequiredTrimmedStringValue(response['status'], 'Kill process response.status');
                readRequiredTrimmedStringValue(response['message'], 'Kill process response.message');
                return { status };
            }),
        getLastSnapshot: () => dependencies.getLastSnapshot(),
        onSortChanged: (state) => dependencies.onSortChanged(state)
    });
    return new ProcessTableManager(processTableDependencies);
};

export { createHardwareProcessController };
export type { CreateHardwareProcessControllerDependencies };

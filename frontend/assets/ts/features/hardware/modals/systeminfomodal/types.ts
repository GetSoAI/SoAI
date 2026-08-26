/* SoAI - Hardware feature system info modal contracts [frontend/assets/ts/features/hardware/modals/systeminfomodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContractTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

interface SystemInfoModalHost {
    modals: ModalPresenterApi;
    domHasClass(element: Element, className: string): boolean;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    updateProperty(target: Element, property: string, value: DomPropertyValue): void;
    addClassName(target: Element, className: string): void;
    removeClassName(target: Element, className: string): void;
    updateText(target: Element, text: string): void;
    setDataAttribute(target: Element, name: string, value: string | null): void;
    getDataAttribute(target: Element, name: string): string | null;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

interface SystemInfoFormattingInput {
    hardware: HardwareSnapshotResponse;
    systemInfo: JsonObject | null;
    plugins: PluginRecord[];
    health: JsonObject | null;
}

interface SystemInfoModalState {
    rawSystemInfo: string;
    anonymizedSystemInfo: string;
    isAnonymized: boolean;
    isOpen: boolean;
}

interface SystemInfoModalDependencies {
    host: SystemInfoModalHost;
}

export type { SystemInfoFormattingInput, SystemInfoModalDependencies, SystemInfoModalHost, SystemInfoModalState };

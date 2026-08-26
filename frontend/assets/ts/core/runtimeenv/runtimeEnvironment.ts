/* SoAI - Frontend runtime environment ownership [frontend/assets/ts/core/runtimeenv/runtimeEnvironment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { type OpenDetachedOptions, type OpenDetachedResult, type OpenWindowInfo, type RuntimeEnvInterface, type WindowMetadata } from '@core/runtimeenv/contracts.ts';
import { Kernel, getKernel } from '@core/runtimeenv/kernel.ts';
import { WindowService, getWindowService } from '@core/runtimeenv/service.ts';

const runtimeEnv: RuntimeEnvInterface = Object.freeze({
    get kernel() {
        return getKernel();
    },
    get windowService() {
        return getWindowService();
    }
});

const openDetachedRuntimeWindow = (pageId: string, options: OpenDetachedOptions = {}): OpenDetachedResult | null => getWindowService().openDetached(pageId, options);

const closeDetachedRuntimeWindowsByPage = (pageId: string): void => {
    const windowService = getWindowService();
    const openWindows = windowService.getOpenWindows();
    for (const openWindow of openWindows) {
        if (openWindow.pageId === pageId) {
            windowService.closeWindow(openWindow.windowId);
        }
    }
};

export { Kernel, WindowService, closeDetachedRuntimeWindowsByPage, getKernel, getWindowService, openDetachedRuntimeWindow, runtimeEnv };
export type { OpenDetachedOptions, OpenDetachedResult, OpenWindowInfo, RuntimeEnvInterface, WindowMetadata };

/* SoAI - Hardware controller and modal construction contracts [frontend/assets/ts/pages/hardware/services/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { HistoryChartRuntime } from '@features/charts/public.ts';
import type { SoAIBenchHistoryModal, SoAIBenchRunModal } from '@features/hardware/public.ts';
import type { HardwareLayoutStorage } from '@pages/hardware/controllers/page/hardwareLayoutController.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';

interface HardwareServiceOwners {
    api: ApiClient;
    storage: HardwareLayoutStorage;
    pageLifecycle: PageLifecycle;
    pageDom: PageDom;
    pageElements: PageUi;
    services: PageServices;
    streaming: PageStreaming;
    feedback: PageFeedback;
    dom: {
        setHTML(element: Element, html: import('@core/security/public.ts').TrustedHtml | string, options?: { escape?: boolean }): void;
        setStyle(element: Element, property: string, value: string | null): void;
        hasClass(element: Element, className: string): boolean;
        getDocument(): Document;
    };
}

interface HardwareGpuControllerDependencies {
    owners: HardwareServiceOwners;
    state: HardwarePageState;
    chartRuntime: HistoryChartRuntime;
    historyModal: SoAIBenchHistoryModal;
    runModal: SoAIBenchRunModal;
}

interface HardwareProcessControllerDependencies {
    owners: HardwareServiceOwners;
    state: HardwarePageState;
}

interface HardwareUiDependencies {
    owners: HardwareServiceOwners;
    renderGpuControls(options?: { only?: string[] | null }): void;
    showSoAIBenchHistory(request: Parameters<SoAIBenchHistoryModal['open']>[0]): Promise<void>;
}

export type { HardwareGpuControllerDependencies, HardwareProcessControllerDependencies, HardwareServiceOwners, HardwareUiDependencies };

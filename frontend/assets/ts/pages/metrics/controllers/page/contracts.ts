/* SoAI - Metrics page ownership and domain contracts [frontend/assets/ts/pages/metrics/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import type { ExportPreviewModal } from '@features/exportpreview/public.ts';
import type { FrontendTelemetryPresenter, MetricsFormatter, MetricsKpiHost, TelemetryService } from '@features/metrics/public.ts';
import type { MetricsPageSession } from '@pages/metrics/controllers/page/MetricsPageSession.ts';
import type { TableBodyContext } from '@pages/metrics/types.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';

interface MetricsRuntimeOwners extends PageLifecycleOwnerHost, PageDomOwnerHost, PageFeedbackOwnerHost, PageResourcesOwnerHost, PageServicesOwnerHost, PageUiOwnerHost, PageLayoutOwnerHost, PageStreamingOwnerHost {
    pageContext: PageContext | null;
    auth: { isAdmin(): boolean };
    stateManager: { status: StatusManager };
}

interface MetricsRuntimeServices {
    metricsFormatter: MetricsFormatter;
    telemetry: TelemetryService | null;
    telemetryPresenter: FrontendTelemetryPresenter | null;
    kpiHost: MetricsKpiHost;
    exportPreviewModal: ExportPreviewModal;
}

interface MetricsRuntimeOperations {
    logger(level: 'debug' | 'info' | 'warn' | 'error', message: string, error?: TelemetryValue): void;
    normalizeMetricsInt(value: number, min?: number): number;
    getCachedUI(id: string): HTMLElement | null;
    resolveTableBodyContext(tableId: string): TableBodyContext | null;
    getDomContext(): Element | null;
    pointBudget(): number;
    requestAnimationFrame(callback: FrameRequestCallback): number;
    cancelAnimationFrame(frameId: number): void;
    syncChartControls(options?: { range?: boolean; candles?: boolean }): Promise<void>;
    fetchCandlestickHistory(options?: { resetView?: boolean; beforeTimestampMs?: number | null }): Promise<void>;
    trimCandlestickData(force?: boolean): boolean;
}

interface MetricsRuntimeContext {
    state: MetricsPageSession;
    owners: MetricsRuntimeOwners;
    metricsServices: MetricsRuntimeServices;
    operations: MetricsRuntimeOperations;
}

type MetricsPageActionsHost = MetricsRuntimeContext;
type MetricsPageAdaptersHost = MetricsRuntimeContext;
type MetricsPageBudgetHost = MetricsRuntimeContext;
type MetricsPageEffectsHost = MetricsRuntimeContext;
type MetricsPageEventHost = MetricsRuntimeContext;
type MetricsPageEventsHost = Pick<MetricsRuntimeContext, 'state' | 'owners'>;
type MetricsPageServiceHost = MetricsRuntimeContext;
type MetricsPageStateHost = MetricsRuntimeContext;

export type { MetricsPageActionsHost, MetricsPageAdaptersHost, MetricsPageBudgetHost, MetricsPageEffectsHost, MetricsPageEventHost, MetricsPageEventsHost, MetricsPageServiceHost, MetricsPageStateHost, MetricsRuntimeContext, MetricsRuntimeOperations, MetricsRuntimeOwners, MetricsRuntimeServices };

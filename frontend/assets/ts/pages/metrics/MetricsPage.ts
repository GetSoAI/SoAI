/* SoAI - Metrics routed page [frontend/assets/ts/pages/metrics/MetricsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { METRICS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { EXPORT_PREVIEW_MODAL_ID } from '@features/exportpreview/public.ts';
import { METRICS_ADVANCED_MODAL_ID, setActiveMetricsAdvancedModalHost } from '@features/metrics/public.ts';
import { isMetricsActionId } from '@pages/metrics/actions.ts';
import { PAGE_ID } from '@pages/metrics/contracts/MetricsPageSupport.ts';
import { setupMetricsPage, teardownMetricsChartUi } from '@pages/metrics/controllers/page/effects.ts';
import { handleMetricsRootClick, handleMetricsRootKeydown, setupMetricsPageUiEffects } from '@pages/metrics/controllers/page/events.ts';
import { resetMetricsValueHistory } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { renderMetricsPageView } from '@pages/metrics/view.ts';
import { MetricsPageRuntime } from '@pages/metrics/controllers/page/MetricsPageRuntime.ts';

class MetricsPage extends StaticBasePage {
    readonly #runtime: MetricsPageRuntime;
    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#runtime = new MetricsPageRuntime({
            storage: this.dependencies.storage,
            pageHost: this.pageHost,
            pageContext: this.pageContext,
            auth: this.dependencies.auth,
            stateManager: this.dependencies.stateManager,
            pageLifecycle: this.pageLifecycle,
            pageDom: this.pageDom,
            feedback: this.feedback,
            pageResources: this.pageResources,
            services: this.services,
            pageElements: this.pageElements,
            layout: this.layout,
            streaming: this.streaming
        });
        this.layout.configure({ onResponsiveLayout: () => this.#runtime.layoutController.onResponsiveLayout() });
    }
    override async prepareInitialContent(_parameters?: JsonObject | null, context: { signal?: AbortSignal } | null = null): Promise<void> {
        const signal = context?.signal;
        if (!signal) {
            throw new Error('MetricsPage prepareInitialContent requires an abort signal');
        }
        await this.#runtime.deferredController.prepare(signal);
    }
    override async startLiveUpdates(parameters?: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.startLiveUpdates(parameters, context);
        setActiveMetricsAdvancedModalHost(this.#runtime.advancedModalHost);
    }
    override async onHide(): Promise<void> {
        this.#runtime.metricsServices.exportPreviewModal.disposeForPageLifecycle('pageHide');
        await super.onHide();
        setActiveMetricsAdvancedModalHost(null);
        requireModalPresenter().close(METRICS_ADVANCED_MODAL_ID, { force: true, restoreFocus: false, reason: 'pageHide' });
        this.pageLifecycle.abortListeners();
        await teardownMetricsChartUi(this.#runtime);
        this.#runtime.deferredController.hide();
        resetMetricsValueHistory(this.#runtime);
    }
    override async onDestroy(): Promise<void> {
        this.#runtime.metricsServices.exportPreviewModal.disposeForPageLifecycle('pageDestroy');
        setActiveMetricsAdvancedModalHost(null);
        requireModalPresenter().close(METRICS_ADVANCED_MODAL_ID, { force: true, restoreFocus: false, reason: 'pageDestroy' });
        this.pageLifecycle.abortListeners();
        this.#runtime.metricsServices.telemetryPresenter?.dispose();
        await teardownMetricsChartUi(this.#runtime);
        this.#runtime.deferredController.hide();
        this.#runtime.state.resetTransientState();
        this.#runtime.layoutController.destroy();
    }
    override getRequiredResources(): string[] {
        return [METRICS, PLUGINS];
    }
    override async setupPage(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#runtime.layoutController.initialize();
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await setupMetricsPage(this.#runtime);
    }
    bindPageEvents(): void {
        const signal = this.pageLifecycle.beginListeners();
        const root = this.resolveHostContainer();
        const exportPreviewModalRoot = requireModalPresenter().requireElement(EXPORT_PREVIEW_MODAL_ID);
        this.#runtime.metricsServices.exportPreviewModal.bindModalEvents({ modalRoot: exportPreviewModalRoot, signal });
        bindPageActionDispatcher({
            label: 'MetricsPage',
            root,
            signal,
            isAction: isMetricsActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void | Promise<void> => handleMetricsRootClick(this.#runtime, action, actionElement, event)
                },
                keydown: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => {
                        if (event instanceof KeyboardEvent) {
                            handleMetricsRootKeydown(this.#runtime, action, actionElement, event);
                        }
                    }
                }
            }
        });
        setupMetricsPageUiEffects(this.#runtime, signal);
        this.pageResources.track(
            this.layout.registerUnsavedChanges({
                hasUnsavedChanges: (): boolean => this.#runtime.layoutController.hasChanges(),
                confirmMessage: i18n.t('common.unsavedChanges'),
                guardId: 'metrics-layout-dirty-guard'
            })
        );
    }
    override async renderView(): Promise<TrustedHtml> {
        return renderMetricsPageView({ getIconSync: (iconName: IconName, options?: IconOptions) => this.services.getIconSync(iconName, options), generateStandardHeader: (options) => this.layout.generateHeader(options) });
    }
}
export { MetricsPage };

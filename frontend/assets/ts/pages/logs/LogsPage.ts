/* SoAI - Logs routed page [frontend/assets/ts/pages/logs/LogsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { TextZoomController } from '@core/TextZoomController.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { bindLogSelectionCopy, CORE_LOG_SOURCE } from '@features/logging/public.ts';
import { LOGS_ACTION_LINE_LIMIT_CHANGE, LOGS_ACTION_SOURCE_CHANGE, isLogsActionId, type LogsActionId } from '@pages/logs/actions.ts';
import { DEFAULT_TEXT_ZOOM } from '@pages/logs/contracts/constants.ts';
import { dispatchLogsPageDelegatedAction } from '@pages/logs/controllers/page/logsPageDelegatedActionController.ts';
import { LogsViewSession } from '@pages/logs/controllers/page/LogsViewSession.ts';
import { loadAvailableLogSources } from '@pages/logs/services/logsources/service.ts';
import { persistLogsSourcePreference, resolveLogsSourcePreference } from '@pages/logs/services/pagecontrols/service.ts';
import { resolveLogLineLimitFromStorage, resolveLogLineOptions } from '@pages/logs/services/preferences/service.ts';
import { openLogsDetachedWindow, subscribeLogsStream } from '@pages/logs/services/service.ts';
import type { LogStreamService, StreamPayload } from '@pages/logs/types.ts';
import { renderLogsPageView } from '@pages/logs/view.ts';

export const PAGE_ID = 'logs';
export const PAGE_MODULE_ID = 'pages.LogsPage';
class LogsPage extends StaticBasePage {
    textZoom = DEFAULT_TEXT_ZOOM;
    textZoomController: TextZoomController | null = null;
    logSource = CORE_LOG_SOURCE;
    availableLogSources: readonly string[] = [CORE_LOG_SOURCE];
    logStreamUnsubscribe: (() => void) | null = null;
    readonly #viewSession: LogsViewSession;
    readonly #logStream: LogStreamService;
    private readonly handleLogStreamPayload = (payload: StreamPayload): void => {
        this.#viewSession.handlePayload(payload);
    };
    #detachActionController: HeaderActionController | null = null;
    constructor(logStream: LogStreamService, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#logStream = logStream;
        this.#viewSession = new LogsViewSession({ document: this.dependencies.dom.getDocument(), pageDom: this.pageDom, storage: this.dependencies.storage });
    }
    override getRequiredResources(): string[] {
        return [];
    }
    protected override async afterInitialization(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterInitialization(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#viewSession.lineLimit = resolveLogLineLimitFromStorage(this.dependencies.storage);
        this.textZoomController = this.textZoomController ?? TextZoomController.createForLogs(this.dependencies.storage);
        this.textZoom = this.textZoomController.initialize({ pageDom: this.pageDom, dom: this.dependencies.dom });
    }
    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        this.availableLogSources = await loadAvailableLogSources(this.dependencies.api);
        if (!this.availableLogSources.includes(CORE_LOG_SOURCE)) {
            throw new Error('Log sources response must include core logs');
        }
        this.logSource = resolveLogsSourcePreference(this.dependencies.storage, this.availableLogSources);
        return {};
    }
    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return renderLogsPageView({
            generateStandardHeader: (options) => this.layout.generateHeader(options),
            getIconSync: (iconName, options) => this.services.getIconSync(iconName, options),
            logLineLimits: resolveLogLineOptions(this.dependencies.storage),
            selectedLineLimit: this.#viewSession.lineLimit,
            logSources: this.availableLogSources,
            selectedLogSource: this.logSource
        });
    }
    override async initializeShell(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#viewSession.initialize();
        this.applyTextZoom();
        this.#viewSession.renderBuffer();
        if (!this.services.isDetached()) {
            this.#detachActionController ??= createHeaderActionController({ actionId: 'detach', contextId: 'logs' });
            this.#detachActionController.show({ onClick: () => openLogsDetachedWindow() });
        }
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.startLogsStream();
    }
    bindPageEvents(): void {
        const ui = this.#viewSession.ui;
        const signal = this.pageLifecycle.beginListeners();
        const dispatchLogsAction = (resolved: { action: LogsActionId; actionElement: HTMLElement & { dataset: DOMStringMap & { action: string } } }): void => {
            dispatchLogsPageDelegatedAction(
                {
                    adjustTextSize: (delta: number): void => this.adjustTextSize(delta),
                    clearLogs: (): void => this.clearLogs(),
                    changeLogLineLimit: (limit: number): void => this.#changeLogLineLimit(limit),
                    changeLogSource: (source: string): void => this.#changeLogSource(source)
                },
                resolved
            );
        };
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'LogsPage',
            isAction: isLogsActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: dispatchLogsAction
                },
                change: {
                    preventDefault: 'never',
                    onAction: dispatchLogsAction
                }
            }
        });
        bindLogSelectionCopy({ root: ui.output, signal, showNotification: (message, type) => this.feedback.show(message, type) });
        ui.root.addEventListener('scroll', this.#viewSession.handleScroll, { signal, passive: true });
    }
    async startLogsStream(): Promise<void> {
        this.logStreamUnsubscribe = subscribeLogsStream({
            moduleValue: this.#logStream,
            logLineLimit: this.#viewSession.lineLimit,
            logSource: this.logSource,
            previousUnsubscribe: this.logStreamUnsubscribe,
            onPayload: this.handleLogStreamPayload
        });
    }
    clearLogs(): void {
        this.#viewSession.clear();
    }
    updateLogLineLimit(newLimit: number): void {
        this.#viewSession.updateLineLimit(newLimit);
    }
    adjustTextSize(delta: number): void {
        if (!isNumber(delta) || !Number.isFinite(delta)) {
            return;
        }
        if (this.textZoomController) {
            this.textZoom = this.textZoomController.adjust({ pageDom: this.pageDom, dom: this.dependencies.dom }, delta);
        }
    }
    applyTextZoom(): void {
        if (this.textZoomController) {
            this.textZoom = this.textZoomController.applyZoom({ pageDom: this.pageDom, dom: this.dependencies.dom });
        }
    }
    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        if (this.logStreamUnsubscribe) {
            this.logStreamUnsubscribe();
            this.logStreamUnsubscribe = null;
        }
        this.#detachActionController?.dispose();
        this.#detachActionController = null;
        this.#viewSession.destroy();
    }

    #changeLogLineLimit(limit: number): void {
        void this.pageLifecycle
            .run(LOGS_ACTION_LINE_LIMIT_CHANGE, async () => {
                this.updateLogLineLimit(limit);
                await this.startLogsStream();
            })
            .catch((error) => {
                errorHandler.warn('LogsPage', 'Failed to change log line limit', error);
            });
    }

    #changeLogSource(source: string): void {
        void this.pageLifecycle
            .run(LOGS_ACTION_SOURCE_CHANGE, async () => {
                await this.updateLogSource(source);
            })
            .catch((error) => {
                errorHandler.warn('LogsPage', 'Failed to change log source', error);
            });
    }

    private async updateLogSource(source: string): Promise<void> {
        const trimmed = isString(source) ? source.trim() : '';
        if (!trimmed) {
            throw new Error('Log source change requires non-empty value');
        }
        if (!this.availableLogSources.includes(trimmed)) {
            throw new Error(`Log source "${trimmed}" is not available`);
        }
        if (trimmed === this.logSource) {
            return;
        }
        this.logSource = trimmed;
        persistLogsSourcePreference(this.dependencies.storage, trimmed);
        this.#viewSession.resetForSourceChange(i18n.t('logs.connecting'));
        await this.startLogsStream();
    }
}
export { LogsPage };

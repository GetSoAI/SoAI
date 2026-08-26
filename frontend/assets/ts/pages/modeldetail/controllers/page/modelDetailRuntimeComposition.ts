/* SoAI - Model detail parameter and test-modal runtime composition [frontend/assets/ts/pages/modeldetail/controllers/page/modelDetailRuntimeComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { TestModalManager, type TestModalManagerHost } from '@features/modeldetail/public.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { StatusManager } from '@core/state/public.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { isCollapseController, isTestModalLogStreamHandle } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import { ParameterViewManager } from '@pages/modeldetail/controllers/ParameterViewManager.ts';
import type { ParameterViewHost, ParameterViewNavigationQueryValue } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { getModelDetailDisplayName, getModelDetailPluginStatus, getModelDetailSourceModelId } from '@pages/modeldetail/controllers/page/state.ts';
import { toModelDetailIconOptions } from '@pages/modeldetail/rendering/modelDetailIconOptions.ts';

interface ModelDetailRuntimeOwners {
    pageDom: PageDom;
    pageResources: PageResources;
    pageElements: PageUi;
    pageLifecycle: PageLifecycle;
    collapsibleCards: PageCollapsibleCards;
    streaming: PageStreaming;
    services: PageServices;
    feedback: PageFeedback;
    storage: PageControlsStorageInput;
    dom: {
        getDocument(): Document;
        getData(element: Element | null, key: string): string | null | undefined;
        resolveAll(selector: string, context?: import('@core/dom/types.ts').DOMQueryRoot): Element[];
        replaceElement(target: Element, newContent: Node | TrustedHtml, context?: Element | null): Element | null;
    };
    layout: PageLayout;
    modalPresenter: ModalPresenterApi;
    router: Router;
    saveRequests: ChangeNotificationSource;
    session: ModelDetailSession;
    statusManager: StatusManager;
}

interface ModelDetailRuntimeComposition {
    streamManager: ReturnType<PageStreaming['runtime']>;
    parameterState: ParameterStateManager;
    parameterView: ParameterViewManager;
    testModalManager: TestModalManager;
}

const composeModelDetailRuntime = (owners: ModelDetailRuntimeOwners): ModelDetailRuntimeComposition => {
    const streamManager = owners.streaming.runtime();
    const parameterState = new ParameterStateManager();
    const parameterView = new ParameterViewManager({ host: createParameterViewDependencies(owners), parameterState });
    const testModalManager = new TestModalManager({ host: createTestModalDependencies(owners, streamManager) });
    return { streamManager, parameterState, parameterView, testModalManager };
};

const createParameterViewDependencies = (owners: ModelDetailRuntimeOwners): ParameterViewHost => ({
    pageDom: owners.pageDom,
    pageResources: owners.pageResources,
    $: (selector, context) => owners.pageDom.optional(selector, context),
    $$: (selector, context) => owners.pageDom.query(selector, context),
    storage: owners.storage,
    setUIValue: (element, value, options) => owners.pageElements.setValue(element, value, options),
    getIconSync: (name, options) => owners.services.getIconFromStringSync(name, options),
    dom: owners.dom,
    router: {
        navigateWithQuery: (page, query) => {
            void owners.router.navigateWithQuery(page, normalizeNavigationQuery(query));
        }
    },
    notifySaveChanged: () => owners.saveRequests.notify(),
    updateParametersBadge: (count) => owners.layout.getTabs()?.updateTabNotifyBadge('parameters', Number(count) || 0)
});

const createTestModalDependencies = (owners: ModelDetailRuntimeOwners, streamManager: ReturnType<PageStreaming['runtime']>): TestModalManagerHost => {
    const status = owners.statusManager;
    const mutate = (element: Element | null, operation: (target: Element) => void): void => {
        if (element) operation(element);
    };
    return {
        model: {
            getDocument: () => owners.dom.getDocument(),
            getModel: () => owners.session.model,
            get modelId() {
                const identifier = owners.session.modelId;
                return isString(identifier) && identifier.trim() ? identifier : null;
            },
            modalPresenter: owners.modalPresenter,
            streamLogs: (source, handlers, options) => {
                const handle = streamManager.connection.streamLogs(source, handlers, options ?? {});
                if (!isTestModalLogStreamHandle(handle)) throw new Error('ModelDetailPage requires streamLogs handle with close()');
                return handle;
            },
            getPluginStatus: () => getModelDetailPluginStatus(owners.session.model),
            getModelDisplayName: () => getModelDetailDisplayName(owners.session.model),
            getModelSourceModelId: () => requireSourceModelId(owners.session.model)
        },
        view: {
            optionalUI: (selector, context) => owners.pageDom.optional(selector, context),
            showNotification: (message, type) => owners.feedback.show(message, type),
            sanitizeText: (value) => owners.services.sanitizeText(value === null || value === undefined ? value : String(value)),
            hasClipboardSupport: () => owners.services.hasClipboardSupport(),
            copyToClipboard: (value, options) => copyModelDetailText(owners, value, options),
            setTimer: (functionValue, delay, options) => requireTimer(owners.pageResources.setTimer(functionValue, delay, normalizeTimerOptions(options))),
            clearTimer: (timerId) => {
                if (isNumber(timerId)) owners.pageResources.clearTimer(timerId);
            },
            toggleClassName: (element, className, force) => mutate(element, (target) => owners.pageDom.toggleClass(target, className, force)),
            addClassName: (element, className) => mutate(element, (target) => owners.pageDom.addClass(target, className)),
            removeClassName: (element, className) => mutate(element, (target) => owners.pageDom.removeClass(target, className)),
            updateText: (element, text) => mutate(element, (target) => owners.pageDom.updateText(target, text)),
            updateHTML: (element, html, options) => mutate(element, (target) => owners.pageDom.updateHtml(target, html, options)),
            updateProperty: (element, property, value) => mutate(element, (target) => owners.pageDom.updateProperty(target, property, value))
        },
        workflow: {
            statusManager: {
                allowedColors: status.listColors(),
                getDescription: (value) => status.getDescription(value),
                normalizeStatus: (value) => status.normalizeStatus(value),
                isError: (value) => status.isError(value),
                createStatusBadge: (value, description) => createStatusBadge(owners, status.createStatusBadge(value, description))
            },
            runWithBoundary: (name, functionValue) => owners.pageLifecycle.run(name, functionValue),
            createLogsCollapseController: (options) => {
                const controller = owners.collapsibleCards.configure(options);
                if (!isCollapseController(controller)) throw new Error('ModelDetailPage configureCardCollapse must return a collapse controller');
                return controller;
            },
            getIconSync: (name, options) => owners.services.getIconFromStringSync(name, toModelDetailIconOptions(options))
        }
    };
};

const normalizeNavigationQuery = (query: Record<string, ParameterViewNavigationQueryValue>): Record<string, string> => {
    const normalized: Record<string, string> = {};
    for (const [key, value] of Object.entries(query)) {
        if (!key) throw new Error('ModelDetailPage router.navigateWithQuery requires non-empty query keys');
        normalized[key] = String(value);
    }
    return normalized;
};

const normalizeTimerOptions = (options?: JsonObject): { repeat?: boolean; immediate?: boolean } => {
    if (!isObject(options)) return {};
    const normalized: { repeat?: boolean; immediate?: boolean } = {};
    if (isBoolean(options['repeat'])) normalized.repeat = options['repeat'];
    if (isBoolean(options['immediate'])) normalized.immediate = options['immediate'];
    return normalized;
};

const requireTimer = (timerId: number | null): number => {
    if (timerId === null) throw new Error('ModelDetail test modal timer was not scheduled');
    return timerId;
};

const requireSourceModelId = (model: ModelRecord | null): string => {
    const identifier = getModelDetailSourceModelId(model);
    if (!isString(identifier) || !identifier.trim()) throw new Error('ModelDetailPage requires a model sourceModelId for test modal rendering');
    return identifier;
};

const createStatusBadge = (owners: ModelDetailRuntimeOwners, badge: HTMLElement | string): HTMLElement => {
    if (badge instanceof HTMLElement) return badge;
    const element = owners.dom.getDocument().createElement('span');
    owners.pageDom.updateText(element, badge);
    return element;
};

const copyModelDetailText = async (owners: ModelDetailRuntimeOwners, value: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void> => {
    try {
        await copyTextWithHostClipboardFeedback(
            {
                copyToClipboard: (text, copyOptions) => owners.services.copyToClipboard(text, copyOptions),
                hasClipboardSupport: () => owners.services.hasClipboardSupport(),
                showNotification: (message, type) => {
                    if (options?.notify) {
                        options.notify(message, type);
                        return;
                    }
                    owners.feedback.show(message, type);
                }
            },
            { text: value, successMessage: i18n.t('common.clipboard.copied'), unavailableMessage: i18n.t('common.clipboard.copyUnavailable'), unavailableType: 'error' }
        );
    } catch (error) {
        errorHandler.error('ModelDetailPage', 'copyToClipboard failed', ensureError(error));
    }
};

export { composeModelDetailRuntime };
export type { ModelDetailRuntimeComposition, ModelDetailRuntimeOwners };

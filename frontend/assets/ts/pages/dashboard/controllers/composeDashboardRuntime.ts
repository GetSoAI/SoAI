/* SoAI - Dashboard runtime ownership composition [frontend/assets/ts/pages/dashboard/controllers/composeDashboardRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { createDashboardRuntime } from '@pages/dashboard/adapters/DashboardRuntimeManager.ts';
import type { DashboardRuntime, DashboardRuntimeDependencies, StatusManagerContract } from '@pages/dashboard/contracts/contracts.ts';
import type { DashboardBlueprint, DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import type { DashboardLogStream } from '@pages/dashboard/widgets/logs/types.ts';
import type { DashboardEditionContribution } from '@core/edition/dashboardContribution.ts';
import { createDashboardSectionSurface } from '@pages/dashboard/rendering/layout/sectionSurfaceComposition.ts';

interface DashboardInfrastructure {
    auth: AuthManager;
    feedback: PageFeedback;
    layout: PageLayout;
    pageDom: PageDom;
    pageElements: PageUi;
    pageResources: PageResources;
    router: Router;
    services: PageServices;
    storage: StorageService;
}

interface DashboardRuntimeStateBindings {
    getBlueprints(): Map<DashboardBlueprintId, DashboardBlueprint> | null;
    getCurrentStatus(): StatusManagerContract | null;
    isDestroyed(): boolean;
}

interface DashboardRuntimeLogBindings {
    ensureReady(): Promise<DashboardLogStream>;
    debug(message: string, detail?: JsonValue | Error | null): void;
    error(message: string, detail?: JsonValue | Error | null): void;
}

interface DashboardRuntimeActionBindings {
    onLogsAction: DashboardRuntimeDependencies['onLogsAction'];
    onImageUploadOpen: DashboardRuntimeDependencies['imageActions']['onUploadOpen'];
    onImageDelete: DashboardRuntimeDependencies['imageActions']['onDelete'];
    onImageToggleFit: DashboardRuntimeDependencies['imageActions']['onToggleFit'];
}

interface DashboardRuntimeCompositionOptions {
    infrastructure: DashboardInfrastructure;
    state: DashboardRuntimeStateBindings;
    logs: DashboardRuntimeLogBindings;
    actions: DashboardRuntimeActionBindings;
    edition: DashboardEditionContribution | null;
}

const composeDashboardRuntime = ({ infrastructure, state, logs, actions, edition }: DashboardRuntimeCompositionOptions): DashboardRuntime => {
    const { auth, feedback, layout, pageDom, pageElements, pageResources, router, services, storage } = infrastructure;
    return createDashboardRuntime({
        host: {
            notify: (message, level) => feedback.show(message, level),
            createElement: (tag, attrs, text) => pageElements.createElement(tag, attrs, text),
            replaceElementContent: (target, content, options) => pageDom.replaceContent(target, content, options),
            flushDOMUpdates: () => pageDom.flush(),
            optionalUI: (selector, context) => pageDom.optional(selector, context ?? undefined),
            requireUI: (selector, context) => pageDom.require(selector, context ?? undefined),
            optionalHTMLElement: (selector, context) => pageDom.optionalHTMLElement(selector, context ?? undefined),
            requireHTMLElement: (selector, context) => pageDom.requireHTMLElement(selector, context ?? undefined),
            sanitizeText: (value) => services.sanitizeText(value),
            getStyleProp: (name) => services.getStyleProperty(name)
        },
        sectionLayoutHost: {
            optionalUI: (selector, context) => pageDom.optional(selector, context ?? undefined),
            optionalHTMLElement: (selector, context) => pageDom.optionalHTMLElement(selector, context ?? undefined),
            requireHTMLElement: (selector, context) => pageDom.requireHTMLElement(selector, context ?? undefined),
            on: (target, event, handler, options) => pageResources.on(target, event, handler, options),
            updateStyle: (element, property, value) => pageDom.updateStyle(element, property, value),
            updateStyles: (element, styles) => pageDom.updateStyles(element, styles),
            applyGridPosition: (element, position) => layout.applyGridPosition(element, position),
            createSection: (id, options) =>
                createDashboardSectionSurface(
                    {
                        createSection: (sectionId, sectionOptions) => pageElements.createSection(sectionId, sectionOptions),
                        createElement: (tag, attributes) => pageElements.createElement(tag, attributes),
                        append: (target, children) => pageDom.append(target, children)
                    },
                    id,
                    options
                ),
            logger: (_level, message, detail) => logs.debug(message, detail)
        },
        sectionLayoutStorage: {
            getLayout: () => storage.getDashboardLayout(),
            saveLayout: (value) => storage.saveDashboardLayout(isJsonObject(value) ? value : null),
            getHiddenSectionIds: () => storage.getHiddenDashboardElements()
        },
        imageCardStorage: {
            getDashboardImageCard: () => storage.getDashboardImageCard(),
            setDashboardImageCard: (value) => storage.setDashboardImageCard(value),
            getDashboardImageCardFit: () => storage.getDashboardImageCardFit(),
            setDashboardImageCardFit: (value) => storage.setDashboardImageCardFit(value)
        },
        memoStorage: {
            getDashboardMemo: () => storage.getDashboardMemo(),
            setDashboardMemo: (value) => storage.setDashboardMemo(value)
        },
        logsHost: {
            storageGet: (key, defaultValue) => storage.get(key, defaultValue),
            storageSet: (key, value) => storage.set(key, value),
            replaceElementContent: (target, content, options) => pageDom.replaceContent(target, content, options),
            flushDOMUpdates: () => pageDom.flush(),
            optionalHTMLElement: (selector, context) => pageDom.optionalHTMLElement(selector, context ?? undefined),
            updateProperty: (element, property, value) => pageDom.updateProperty(element, property, value),
            updateStyle: (element, property, value) => pageDom.updateStyle(element, property, value),
            updateHTML: (element, html, options) => pageDom.updateHtml(element, html, options),
            ensureLogStreamReady: () => logs.ensureReady(),
            logError: (message, detail) => logs.error(message, detail),
            isDestroyed: () => state.isDestroyed(),
            showNotification: (message, type) => feedback.show(message, type)
        },
        timers: {
            setTimer: (callback, delay, options) => pageResources.setTimer(callback, delay, options),
            clearTimer: (timerId) => pageResources.clearTimer(timerId)
        },
        on: (target, event, handler, options) => pageResources.on(target, event, handler, options),
        navigate: (route) => {
            terminateHandledPromise(router.navigate(route));
        },
        getBlueprints: () => state.getBlueprints(),
        getCurrentStatus: () => state.getCurrentStatus(),
        getDashboardLocked: () => storage.getDashboardLocked(),
        getClockSecondsEnabled: () => storage.getClockSecondsEnabled(),
        isAdmin: () => auth.isAdmin(),
        isDestroyed: () => state.isDestroyed(),
        logDebug: (message, detail) => logs.debug(message, detail),
        genericStorage: {
            get: (key, defaultValue) => storage.get(key, defaultValue),
            set: (key, value) => storage.set(key, value)
        },
        onLogsAction: actions.onLogsAction,
        imageActions: {
            onUploadOpen: actions.onImageUploadOpen,
            onDelete: actions.onImageDelete,
            onToggleFit: actions.onImageToggleFit
        },
        edition
    });
};

export { composeDashboardRuntime };
export type { DashboardInfrastructure, DashboardRuntimeActionBindings, DashboardRuntimeCompositionOptions, DashboardRuntimeLogBindings, DashboardRuntimeStateBindings };

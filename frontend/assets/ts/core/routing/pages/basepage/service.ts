/* SoAI - Shared routing basepage service [frontend/assets/ts/core/routing/pages/basepage/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPerformance, getRequestAnimationFrame } from '@core/environment/public.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { revealMountedPageSection } from '@core/pageTransitions.ts';
import { replaceContentPreservingPageOutletSlots } from '@core/pageoutlet/slots.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { isHTMLElement, isObject } from '@core/typeGuards.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageRuntime } from '@core/runtime/PageRuntime.ts';
import type { PageRuntimePhases } from '@core/runtime/pageRuntimeContracts.ts';

interface BasePageInitializeHost {
    pageId: string;
    runtime: PageRuntime;
    phases: PageRuntimePhases;
    pageHost: PageHost;
    pageDom: PageDom;
    services: PageServices;
    layout: PageLayout;
    isDestroyed: boolean;
    isInitialized: boolean;
    resetLifecycleState: () => void;
    render: (parameters?: JsonObject | null) => Promise<TrustedHtml>;
    initialize: (parameters: JsonObject | null, context: { signal?: AbortSignal }) => Promise<boolean>;
    onRefresh: (parameters: JsonObject | null, context: { signal?: AbortSignal }) => Promise<void>;
}

const isBasePageReloadNavigation = (): boolean => {
    const performanceObject = getPerformance();
    const entries = performanceObject.getEntriesByType('navigation');
    for (const entry of entries) {
        if (!isObject(entry)) {
            continue;
        }
        if ('type' in entry && entry.type === 'reload') {
            return true;
        }
    }
    return false;
};

const isDeferredRevealContainer = (container: HTMLElement): boolean => container.dataset['pageOutletRoot'] === 'true' || container.dataset['pageHostPrepared'] === 'true';

const initializeBasePageLifecycle = async (host: BasePageInitializeHost, parameters?: JsonObject | null, options: { signal?: AbortSignal } = {}): Promise<void> => {
    const signal = options.signal ?? null;
    const shouldAbort = (): boolean => signalAborted(signal);
    if (shouldAbort()) return;
    const isReload = isBasePageReloadNavigation();
    host.runtime.cancel('reinitialize');
    const container = host.pageHost.resolveContainer();
    if (!isHTMLElement(container)) {
        throw err('Host container required');
    }
    if (shouldAbort()) return;
    if (host.isDestroyed || (!container.hasChildNodes() && host.isInitialized)) {
        host.resetLifecycleState();
    }
    if (!host.isInitialized || !container.hasChildNodes()) {
        const markup = await host.render(parameters);
        if (shouldAbort()) return;
        if (!isTrustedHtml(markup) || !markup.html.trim()) {
            const renderError = err('Render failure');
            throw renderError;
        }
        replaceContentPreservingPageOutletSlots(container, () => {
            host.pageDom.updateHtml(container, markup, { escape: false });
        });
        host.pageDom.flush();
        host.services.clearDomCache();
        host.layout.applyHeaderStats(container);
        host.pageDom.flush();
        const frame = getRequestAnimationFrame();
        await new Promise<void>((resolve) => frame(() => frame(() => resolve())));
        if (shouldAbort()) return;
        await host.initialize(parameters ?? null, signal ? { signal } : {});
    } else if (isReload) {
        if (shouldAbort()) return;
        await host.onRefresh(parameters ?? null, signal ? { signal } : {});
        if (shouldAbort()) return;
    }
    if (shouldAbort()) return;
    host.runtime.start(parameters ?? {}, host.phases);
    if (!isDeferredRevealContainer(container)) {
        await host.runtime.whenReady({ waitForReveal: false });
        if (shouldAbort()) return;
        revealMountedPageSection(container);
        host.pageDom.flush();
        host.runtime.allowReveal();
    }
};

const runBasePageStandardSetup = (services: PageServices, layout: PageLayout): void => {
    services.clearDomCache();
    layout.setupResponsive();
    layout.setupHeaderStats();
    layout.attachHeaderAnimator();
    layout.attachHeaderCtaConfirmation();
    layout.initializePageActions();
};

export { initializeBasePageLifecycle, runBasePageStandardSetup };

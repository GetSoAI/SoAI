/* SoAI - Dashboard trusted product contribution contracts [frontend/assets/ts/core/edition/dashboardContribution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementOptions } from '@core/dom/dom.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface DashboardTimerControl {
    setTimer: (callback: () => void, delay: number, options?: { repeat?: boolean; immediate?: boolean }) => number | null;
    clearTimer: (id: number | null) => void;
}

interface DashboardHost {
    notify: (message: string, level: 'error' | 'success' | 'info' | 'warning') => void;
    createElement: (tag: string, attrs?: ElementOptions, text?: string) => Element;
    replaceElementContent: (target: Element, content: string | TrustedHtml | DocumentFragment | HTMLElement, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
    optionalUI: (selector: string, context?: Element | null) => Element | null;
    requireUI: (selector: string, context?: Element | null) => Element;
    optionalHTMLElement: (selector: string, context?: Element | null) => HTMLElement | null;
    requireHTMLElement: (selector: string, context?: Element | null) => HTMLElement;
    sanitizeText: (value: string) => string;
    getStyleProp: (name: string) => string | null;
}

interface DashboardProductSectionController {
    render: () => void;
    subscribe: (listener: () => void) => () => void;
}

interface DashboardQuickActionContribution {
    readonly pageId: string;
    readonly icon: IconName;
    readonly getLabel: () => string;
}

interface DashboardEditionContribution {
    readonly getTitle: () => string;
    readonly getSubtitle: () => string;
    readonly quickActions: readonly DashboardQuickActionContribution[];
    readonly createSection: (dependencies: { host: DashboardHost; isDestroyed: () => boolean }) => DashboardProductSectionController;
}

export type { DashboardEditionContribution, DashboardHost, DashboardProductSectionController, DashboardQuickActionContribution, DashboardTimerControl };

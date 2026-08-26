/* SoAI - Dashboard page section state controller [frontend/assets/ts/pages/dashboard/controllers/dashboardSectionStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementOptions } from '@core/dom/dom.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface DashboardSectionStateHost {
    createElement: (tag: string, attrs?: ElementOptions, text?: string) => Element;
    replaceElementContent: (target: Element, content: string | TrustedHtml | DocumentFragment | HTMLElement, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
}

const renderDashboardSectionState = (host: DashboardSectionStateHost, content: HTMLElement, className: string, text: string): void => {
    const node = host.createElement('div', { className }, text);
    host.replaceElementContent(content, narrowHTMLElement(node, 'dashboard section state'), { escape: false });
    host.flushDOMUpdates();
};

export { renderDashboardSectionState };

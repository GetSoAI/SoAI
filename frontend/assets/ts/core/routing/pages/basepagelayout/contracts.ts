/* SoAI - Shared routing base page layout contracts [frontend/assets/ts/core/routing/pages/basepagelayout/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { DOMTarget } from '@core/dom/dom.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';

interface BasePageLayoutSanitizerContract {
    attribute: (value: JsonValue | undefined) => string;
}

interface BasePageLayoutPageContextContract {
    sanitizer: BasePageLayoutSanitizerContract;
}

interface BasePageLayoutHost extends PageServicesOwnerHost {
    pageId: string;
    pageContext: BasePageLayoutPageContextContract;
    getUI: (selector: string | Element, context?: Element) => Element | null;
    queryUI: (selector: string | Element | string[], context?: Element) => Element[];
    on: (target: EventTarget, eventName: string, listener: EventListener, options?: AddEventListenerOptions) => () => void;
    trackDisposable: <T extends DisposableResource>(resource: T, onDispose?: (value: T) => void) => T;
    updateStyles: (target: DOMTarget, styles: Record<string, string | null>, context?: Element | Document | null) => void;
    updateStyle: (target: DOMTarget, property: string, value: string | null, context?: Element | Document | null) => void;
    updateHTML: (target: DOMTarget, html: TrustedHtml | string, options?: { escape?: boolean; context?: Element | Document | null }) => void;
    updateProperty: (target: DOMTarget, property: string, value: DomPropertyValue, context?: Element | Document | null) => void;
    addClassName: (target: DOMTarget, classes: string | string[], context?: Element | Document | null) => void;
    removeClassName: (target: DOMTarget, classes: string | string[], context?: Element | Document | null) => void;
    setDataAttribute: (target: DOMTarget, name: string, value: string | null, context?: Element | Document | null) => void;
    flushDOMUpdates: () => void;
    isDestroyed?: boolean;
}

export type { BasePageLayoutHost, BasePageLayoutPageContextContract, BasePageLayoutSanitizerContract };

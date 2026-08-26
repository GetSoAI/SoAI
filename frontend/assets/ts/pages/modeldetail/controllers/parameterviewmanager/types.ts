/* SoAI - Model detail page control layer parameter view manager public contracts [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMQueryRoot } from '@core/dom/types.ts';
import type { PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

type ModificationOptions = { suppressCallbacks?: boolean };
type ParameterViewNavigationQueryValue = string | number | boolean | bigint;

type ParameterElementCache = Map<string, Element>;

interface ParameterViewFilters {
    search: string;
    category: string;
    group: string;
}

interface ParameterViewHost extends PageDomOwnerHost, PageResourcesOwnerHost {
    $: (selector: string, context?: Element) => Element | null;
    $$: (selector: string, context?: Element) => Element[];
    storage: PageControlsStorageInput;
    setUIValue: (element: Element, value: string, options?: { attribute?: string }) => void;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    dom: {
        getData: (element: Element | null, key: string) => string | null | undefined;
        resolveAll: (selector: string, context?: DOMQueryRoot) => Element[];
        replaceElement: (target: Element, newContent: Node | TrustedHtml, context?: Element | null) => Element | null;
    };
    router?: {
        navigateWithQuery?: (page: string, query: Record<string, ParameterViewNavigationQueryValue>) => void;
    };
    notifySaveChanged: () => void;
    updateParametersBadge: (count: number) => void;
}

interface ParameterViewManagerOptions {
    host: ParameterViewHost;
    parameterState: ParameterStateManager;
}

export type { ModificationOptions, ParameterElementCache, ParameterViewFilters, ParameterViewHost, ParameterViewManagerOptions, ParameterViewNavigationQueryValue };

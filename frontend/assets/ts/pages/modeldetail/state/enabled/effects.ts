/* SoAI - Model detail page state enabled effects [frontend/assets/ts/pages/modeldetail/state/enabled/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isBoolean } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelDetailEnabledToggleHost extends PageDomOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
}

const populateModelDetailEnabledToggle = (host: ModelDetailEnabledToggleHost): void => {
    const container = host.pageDom.optionalHTMLElement('modeldetail-enabled-toggle');
    if (!container) {
        return;
    }
    if (!host.model || host.isVirtualModel()) {
        host.pageDom.addClass(container, 'u-hidden');
        return;
    }
    const checkbox = dom.resolve('#modeldetail-enabled-checkbox', container);
    if (!(checkbox instanceof HTMLInputElement) || checkbox.type !== 'checkbox') {
        throw new TypeError('#modeldetail-enabled-checkbox must be an HTMLInputElement[type=checkbox]');
    }
    const enabledValue = host.model.isEnabled;
    const enabled = isBoolean(enabledValue) ? enabledValue : true;
    host.pageDom.updateProperty(checkbox, 'checked', enabled);
    host.pageDom.removeClass(container, 'u-hidden');
};

export { populateModelDetailEnabledToggle };
export type { ModelDetailEnabledToggleHost };

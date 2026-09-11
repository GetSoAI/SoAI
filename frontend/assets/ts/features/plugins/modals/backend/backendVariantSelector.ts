/* SoAI - Frontend backend variant selector [frontend/assets/ts/features/plugins/modals/backend/backendVariantSelector.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { normalizeBackendVariantOptions, type BackendVariantOption } from '@features/plugins/modals/backend/backendVariantOptions.ts';
import type { BackendManagerSecurity } from '@features/plugins/modals/backend/backendTypes.ts';

interface BackendVariantSelectorViewPort {
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    updateHTML(target: Element | string, html: TrustedHtml | string, options?: { escape?: boolean; context?: Element | Document | null }): void;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
}

interface BackendVariantSelectorOperationsPort {
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    getBackendVariants(pluginName: string): Promise<BackendVariantsResponse>;
    saveBackendVariantSelection(pluginName: string, variantId: string): Promise<BackendVariantsResponse>;
}

interface BackendVariantSelectorHost {
    view: BackendVariantSelectorViewPort;
    operations: BackendVariantSelectorOperationsPort;
}

interface BackendVariantSelectorDependencies {
    host: BackendVariantSelectorHost;
    security: BackendManagerSecurity;
}

interface BackendVariantSelectorLoadOptions {
    disabled: boolean;
    isCurrent(): boolean;
}

const renderOptions = (dependencies: BackendVariantSelectorDependencies, options: BackendVariantOption[], selected: string, installed: string | null): string => {
    const esc = (value: string): string => dependencies.security.escapeHtml(value);
    const attr = (value: string): string => dependencies.security.escapeAttribute(value);
    return options
        .map((option) => {
            const selectedAttr = option.id === selected ? ' selected' : '';
            const disabledAttr = option.selectable ? '' : ' disabled';
            const tooltip = option.unavailableReason || option.description;
            const title = tooltip ? ` data-tooltip="${attr(tooltip)}"` : '';
            const label = option.id === installed ? i18n.t('plugins.modal.backendVariants.installedOption', { variant: option.label }) : option.label;
            return [`<option value="${attr(option.id)}"${selectedAttr}${disabledAttr}${title}>`, esc(label), '</option>'].join('');
        })
        .join('');
};

const renderSelector = (dependencies: BackendVariantSelectorDependencies, target: HTMLElement, payload: BackendVariantsResponse, disabled: boolean): void => {
    const normalized = normalizeBackendVariantOptions(payload);
    const disabledAttr = disabled ? ' disabled' : '';
    const selectorHtml = toTrustedUiHtml(`
        <span class="plugin-info-details backend-variant-selector">
        <span class="dropdown-select backend-variant-select-shell">
        <select class="backend-variant-select"${disabledAttr}>
        ${renderOptions(dependencies, normalized.options, normalized.selected, normalized.installed)}
        </select>
        </span>
        </span>
    `);
    dependencies.host.view.updateHTML(target, selectorHtml, { escape: false });
};

const loadBackendVariantSelector = async (dependencies: BackendVariantSelectorDependencies, modalId: string, modalRoot: HTMLElement, pluginName: string, options: BackendVariantSelectorLoadOptions): Promise<BackendVariantsResponse | null> => {
    const target = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'variant-selector'), modalRoot);
    const loadingHtml = toTrustedUiHtml(`<div class="plugin-info-details">${i18n.t('plugins.modal.backendVariants.loading')}</div>`);
    dependencies.host.view.updateHTML(target, loadingHtml, { escape: false });
    try {
        const payload = await dependencies.host.operations.getBackendVariants(pluginName);
        if (!options.isCurrent()) {
            return null;
        }
        renderSelector(dependencies, target, payload, options.disabled);
        const select = dependencies.host.view.optionalHTMLElement('.backend-variant-select', target);
        if (!(select instanceof HTMLSelectElement)) {
            throw new Error('Backend variant selector did not render a select element');
        }
        select.dataset['previousValue'] = select.value;
        select.dataset['operationDisabled'] = options.disabled ? 'true' : 'false';
        select.dataset['saving'] = 'false';
        dependencies.host.view.on(select, 'change', (): void => {
            terminateHandledPromise(saveBackendVariantSelection(dependencies, select, pluginName, options.isCurrent));
        });
        return payload;
    } catch (error) {
        if (!options.isCurrent()) {
            return null;
        }
        errorHandler.error('BackendVariantSelector', 'Failed to load backend variants', ensureError(error));
        const errorHtml = toTrustedUiHtml(`<div class="form-disclaimer">${i18n.t('plugins.modal.backendVariants.loadFailed')}</div>`);
        dependencies.host.view.updateHTML(target, errorHtml, { escape: false });
        return null;
    }
};

const saveBackendVariantSelection = async (dependencies: BackendVariantSelectorDependencies, select: HTMLSelectElement, pluginName: string, isCurrent: () => boolean): Promise<void> => {
    const previousValue = select.dataset['previousValue'] || select.value;
    const nextValue = select.value;
    select.dataset['previousValue'] = previousValue;
    select.dataset['saving'] = 'true';
    dependencies.host.view.updateProperty(select, 'disabled', true);
    try {
        await dependencies.host.operations.saveBackendVariantSelection(pluginName, nextValue);
        if (isCurrent()) {
            select.dataset['previousValue'] = nextValue;
        }
    } catch (error) {
        errorHandler.error('BackendVariantSelector', 'Failed to save backend variant', ensureError(error));
        if (isCurrent()) {
            select.value = previousValue;
            dependencies.host.operations.showNotification(i18n.t('plugins.modal.backendVariants.saveFailed'), 'error');
        }
    } finally {
        if (isCurrent()) {
            select.dataset['saving'] = 'false';
            dependencies.host.view.updateProperty(select, 'disabled', select.dataset['operationDisabled'] === 'true');
        }
    }
};

const setBackendVariantSelectorDisabled = (host: BackendVariantSelectorHost, modalId: string, modalRoot: HTMLElement, disabled: boolean): void => {
    const select = host.view.optionalHTMLElement(`${modalUiSelector(modalId, 'variant-selector')} .backend-variant-select`, modalRoot);
    if (select) {
        select.dataset['operationDisabled'] = disabled ? 'true' : 'false';
        host.view.updateProperty(select, 'disabled', disabled || select.dataset['saving'] === 'true');
    }
};

const requireBackendVariantSelectorValue = (host: BackendVariantSelectorHost, modalId: string, modalRoot: HTMLElement): string => {
    const select = host.view.requireHTMLElement(`${modalUiSelector(modalId, 'variant-selector')} .backend-variant-select`, modalRoot);
    if (!(select instanceof HTMLSelectElement)) {
        throw new TypeError('Backend variant selector requires an HTMLSelectElement');
    }
    return select.value;
};

export { loadBackendVariantSelector, requireBackendVariantSelectorValue, setBackendVariantSelectorDisabled };
export type { BackendVariantSelectorHost, BackendVariantSelectorLoadOptions };

/* SoAI - Model detail page control layer parameter view manager [frontend/assets/ts/pages/modeldetail/controllers/ParameterViewManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ParameterTemplateOptions, ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { FILTER_ALL_VALUE, FILTER_CATEGORY_PREFIX, FILTER_GROUP_PREFIX, PARAMETERS_INTERFACE_ID } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { applyFilters, disposeEventHandlers, populateFilterOptions, refreshElementCache, requireElement, resolveElement, updateParameterUi } from '@pages/modeldetail/controllers/parameterviewmanager/dom.ts';
import { applyDefaultHighlights, createParameterFieldStateTracker, refreshModificationState, resetParameterValue, setParameterDefaultState, updateParameterValue } from '@pages/modeldetail/controllers/parameterviewmanager/effects.ts';
import { bindParameterControls } from '@pages/modeldetail/controllers/parameterviewmanager/events.ts';
import { bindParameterLayoutLanes } from '@pages/modeldetail/controllers/parameterviewmanager/parameterLayoutLanesManager.ts';
import { getArrayValueWithAppend, getArrayValueWithRemoval, isParameterUsingDefault, parseJsonParameterValue, setArrayItemValue } from '@pages/modeldetail/controllers/parameterviewmanager/state.ts';
import type { ParameterElementCache, ParameterViewFilters, ParameterViewHost, ParameterViewManagerOptions } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { createTemplateOptions, renderNoParameters, renderParameters, renderVirtualModel } from '@pages/modeldetail/controllers/parameterviewmanager/view.ts';
import { renderParameterControl } from '@pages/modeldetail/widgets/parametertemplates/view.ts';

class ParameterViewManager {
    private readonly host: ParameterViewHost;
    private readonly state: ParameterViewManagerOptions['parameterState'];
    private readonly filters: ParameterViewFilters = {
        search: '',
        category: FILTER_ALL_VALUE,
        group: FILTER_ALL_VALUE
    };
    private icons: Record<string, TrustedHtml> = {};
    private model: ModelRecord | null = null;
    private virtualModel = false;
    private readonly elementCache: ParameterElementCache = new Map();
    private readonly eventDisposers: Array<() => void> = [];
    private readonly boundElements = new Set<Element>();
    private readonly fieldStateTracker: FieldStateTracker;
    constructor({ host, parameterState }: ParameterViewManagerOptions) {
        if (!host) {
            throw new Error('ParameterViewManager requires a host');
        }
        this.host = host;
        this.state = parameterState;
        this.fieldStateTracker = createParameterFieldStateTracker(this.state, (key: string) => resolveElement(this.host, this.elementCache, key));
    }
    setIcons(icons: Record<string, TrustedHtml> = {}): void {
        this.icons = icons;
    }
    setModel(model: ModelRecord | null): void {
        this.model = model ?? null;
        this.virtualModel = Boolean(model?.type === 'virtual');
    }
    setVirtualModel(isVirtual: boolean): void {
        this.virtualModel = Boolean(isVirtual);
    }
    handleParametersApplied(): void {
        this.host.updateParametersBadge(this.state.count);
        this.fieldStateTracker.clearAll();
        this.clearElementCache();
    }
    clearElementCache(): void {
        this.elementCache.clear();
    }
    refreshElementCache(): void {
        refreshElementCache(this.host, this.elementCache);
    }
    resolveElement(parameterKey: string): Element | null {
        return resolveElement(this.host, this.elementCache, parameterKey);
    }
    getTemplateOptions(): ParameterTemplateOptions {
        return createTemplateOptions(this.state, this.icons);
    }
    renderInterface(isVirtualModel?: boolean, model?: ModelRecord | null): void {
        if (typeof isVirtualModel === 'boolean') {
            this.virtualModel = isVirtualModel;
        }
        if (model !== undefined) {
            this.setModel(model);
        }
        const container = requireElement(this.host, PARAMETERS_INTERFACE_ID);
        this.disposeEventHandlers();
        this.clearElementCache();
        if (this.virtualModel) {
            renderVirtualModel(this.host, container, this.model);
            return;
        }
        if (this.state.count === 0) {
            renderNoParameters(this.host, container, this.icons);
            return;
        }
        renderParameters(this.host, this.state, container, this.getTemplateOptions());
        this.eventDisposers.push(bindParameterLayoutLanes(container));
        this.refreshElementCache();
        const filterSelection = this.populateFilterOptions();
        this.refreshModificationState();
        this.applyDefaultHighlights();
        this.applyInvalidHighlights();
        this.handleFilterSelection(filterSelection);
        this.bindParameterControls(container);
    }
    private bindParameterControls(container: Element): void {
        bindParameterControls({
            host: this.host,
            container,
            boundElements: this.boundElements,
            eventDisposers: this.eventDisposers,
            onUpdateArrayItemValue: (parameterKey: string, index: number, value: ParameterValue) => this.updateArrayItemValue(parameterKey, index, value),
            onUpdateParameter: (parameterKey: string, value: ParameterValue) => this.updateParameter(parameterKey, value),
            onUpdateJsonParameter: (parameterKey: string, json: string, textareaId: string) => this.updateJsonParameter(parameterKey, json, textareaId),
            onSetParameterValidity: (parameterKey: string, valid: boolean) => this.setParameterValidity(parameterKey, valid)
        });
    }
    disposeEventHandlers(): void {
        disposeEventHandlers(this.eventDisposers, this.boundElements);
    }
    setSearchFilter(query: string | null): void {
        this.filters.search = normalizeSearchMatchQuery(query);
        this.applyFilters();
    }
    clearSearchFilter(): void {
        this.setSearchFilter('');
    }
    handleFilterSelection(value: string | null): void {
        const selection = value ?? '';
        this.filters.category = selection.startsWith(FILTER_CATEGORY_PREFIX) ? selection.substring(FILTER_CATEGORY_PREFIX.length) : FILTER_ALL_VALUE;
        this.filters.group = selection.startsWith(FILTER_GROUP_PREFIX) ? selection.substring(FILTER_GROUP_PREFIX.length) : FILTER_ALL_VALUE;
        this.applyFilters();
    }
    applyFilters(): void {
        applyFilters(this.host, this.state, this.filters, this.elementCache);
    }
    populateFilterOptions(): string {
        return populateFilterOptions(this.host, this.state);
    }
    applyDefaultHighlights(): void {
        applyDefaultHighlights({
            host: this.host,
            state: this.state,
            resolveElement: (parameterKey: string) => this.resolveElement(parameterKey)
        });
    }
    applyInvalidHighlights(): void {
        this.fieldStateTracker.reapplyDomState();
    }
    private setParameterDefaultState(parameterKey: string, isDefault: boolean): void {
        setParameterDefaultState(this.host, (key: string) => this.resolveElement(key), parameterKey, isDefault);
    }
    setParameterModifiedState(parameterKey: string, isModified: boolean): void {
        this.fieldStateTracker.setModified(parameterKey, isModified);
    }
    updateParameter(parameterKey: string, value: ParameterValue): void {
        updateParameterValue(
            {
                host: this.host,
                state: this.state,
                resolveElement: (key: string) => this.resolveElement(key),
                setParameterModifiedState: (key: string, isModified: boolean) => this.setParameterModifiedState(key, isModified),
                handleModificationStateChange: () => this.handleModificationStateChange()
            },
            parameterKey,
            value
        );
        const linkedParameterKey = this.state.getLinkedParameterKey(parameterKey);
        if (linkedParameterKey) {
            const linkedParameter = this.state.getParameter(linkedParameterKey);
            if (linkedParameter) {
                this.updateParameterUI(linkedParameterKey, linkedParameter.currentValue ?? null);
                this.setParameterDefaultState(linkedParameterKey, isParameterUsingDefault(this.state, linkedParameterKey));
                this.setParameterModifiedState(linkedParameterKey, this.state.isParameterModified(linkedParameterKey));
            }
        }
    }
    refreshModificationState(): void {
        refreshModificationState(
            this.state,
            (key: string, isModified: boolean) => this.setParameterModifiedState(key, isModified),
            () => this.handleModificationStateChange()
        );
    }
    handleModificationStateChange(): void {
        this.updateSaveButton();
    }
    updateSaveButton(): void {
        this.host.notifySaveChanged();
    }
    setParameterValidity(parameterKey: string, valid: boolean): void {
        this.fieldStateTracker.setInvalid(parameterKey, valid ? null : 'invalid');
        this.host.notifySaveChanged();
    }
    updateJsonParameter(parameterKey: string, json: string, textareaId: string): void {
        const validation = this.host.pageDom.optional(`${textareaId}-validation`);
        if (!validation) {
            return;
        }
        let parsed: ParameterValue;
        try {
            parsed = parseJsonParameterValue(json);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('ParameterViewManager', 'Invalid JSON parameter input', runtimeError);
            this.host.pageDom.updateText(validation, i18n.t('modelDetail.parameters.invalidJson'));
            validation.className = 'json-validation error';
            this.setParameterValidity(parameterKey, false);
            return;
        }
        this.setParameterValidity(parameterKey, true);
        this.updateParameter(parameterKey, parsed);
        this.host.pageDom.updateText(validation, '');
        validation.className = 'json-validation';
    }
    addArrayItem(parameterKey: string): void {
        const next = getArrayValueWithAppend(this.state, parameterKey);
        if (!next) {
            return;
        }
        this.updateParameter(parameterKey, next);
        this.rerenderArrayInput(parameterKey);
    }
    removeArrayItem(parameterKey: string, index: number): void {
        const next = getArrayValueWithRemoval(this.state, parameterKey, index);
        if (!next) {
            return;
        }
        this.updateParameter(parameterKey, next);
        this.rerenderArrayInput(parameterKey);
    }
    updateArrayItemValue(parameterKey: string, index: number, value: ParameterValue): void {
        const update = setArrayItemValue(this.state, parameterKey, index, value);
        if (!update) {
            return;
        }
        this.setParameterDefaultState(parameterKey, isParameterUsingDefault(this.state, parameterKey));
        this.setParameterModifiedState(parameterKey, update.isModified);
        this.handleModificationStateChange();
    }
    rerenderArrayInput(parameterKey: string): void {
        const wrapper = this.host.$(`.array-input-wrapper[data-param="${CSS.escape(parameterKey)}"]`);
        const parameter = this.state.getParameter(parameterKey);
        if (!wrapper || !parameter) {
            return;
        }
        const newMarkup = renderParameterControl({ key: parameterKey, ...parameter }, this.getTemplateOptions());
        const nextWrapper = this.host.dom.replaceElement(wrapper, toTrustedUiHtml(newMarkup));
        if (!nextWrapper) {
            throw new Error('Array input rerender failed');
        }
        this.disposeEventHandlers();
        this.refreshElementCache();
        const container = nextWrapper.closest('.parameters-content');
        if (!container) {
            throw new Error('Parameters container missing after array rerender');
        }
        this.bindParameterControls(container);
        this.eventDisposers.push(bindParameterLayoutLanes(container));
    }
    updateParameterUI(parameterKey: string, value: ParameterValue): void {
        updateParameterUi(this.host, this.state, parameterKey, value, (key: string) => this.rerenderArrayInput(key));
    }
    resetParameter(parameterKey: string): void {
        this.setParameterValidity(parameterKey, true);
        resetParameterValue({
            state: this.state,
            parameterKey,
            updateParameterUI: (key: string, value: ParameterValue) => this.updateParameterUI(key, value),
            setParameterDefaultState: (key: string, isDefault: boolean) => this.setParameterDefaultState(key, isDefault),
            setParameterModifiedState: (key: string, isModified: boolean) => this.setParameterModifiedState(key, isModified),
            handleModificationStateChange: () => this.handleModificationStateChange()
        });
    }
    resetAllParameters(): void {
        this.state.getParameterKeys().forEach((key) => this.resetParameter(key));
    }
    hasParameterChanges(): boolean {
        return this.fieldStateTracker.hasPendingChanges();
    }
    areParametersValid(): boolean {
        return this.fieldStateTracker.isValid();
    }
    getModifiedParameterKeys(): string[] {
        return this.fieldStateTracker.getModifiedKeys();
    }
    dispose(): void {
        this.disposeEventHandlers();
        this.clearElementCache();
        this.model = null;
    }
}
export { ParameterViewManager };
export type { ParameterViewHost, ParameterViewManagerOptions };

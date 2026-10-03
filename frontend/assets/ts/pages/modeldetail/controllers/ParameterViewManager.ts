/* SoAI - Model detail page control layer parameter view manager [frontend/assets/ts/pages/modeldetail/controllers/ParameterViewManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ParameterGroup, ParameterTemplateOptions, ParameterValue, ParameterView } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { PARAMETER_GROUPS, PARAMETER_REVERT_SELECTOR, PARAMETERS_INTERFACE_ID } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { applyFilters, disposeEventHandlers, refreshElementCache, requireElement, resolveElement, updateParameterUi } from '@pages/modeldetail/controllers/parameterviewmanager/dom.ts';
import { createParameterFieldStateTracker, refreshModificationState, resetParameterValue, syncParameterCustomizedState, updateParameterValue } from '@pages/modeldetail/controllers/parameterviewmanager/effects.ts';
import { bindParameterControls } from '@pages/modeldetail/controllers/parameterviewmanager/events.ts';
import { ParameterCategoryRailController } from '@pages/modeldetail/controllers/parameterviewmanager/parameterCategoryRailController.ts';
import { persistModelDetailParameterGroup, readModelDetailParameterGroup } from '@pages/modeldetail/controllers/parameterviewmanager/parameterViewControlsManager.ts';
import { getArrayValueWithAppend, getArrayValueWithRemoval, parseJsonParameterValue, setArrayItemValue } from '@pages/modeldetail/controllers/parameterviewmanager/state.ts';
import type { BoundParameterEvents, ParameterElementCache, ParameterViewFilters, ParameterViewHost, ParameterViewManagerOptions } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { createTemplateOptions, renderNoParameters, renderParameters, renderVirtualModel } from '@pages/modeldetail/controllers/parameterviewmanager/view.ts';
import { resolveParameterInputId } from '@pages/modeldetail/widgets/parametertemplates/state.ts';
import { renderParameterControl } from '@pages/modeldetail/widgets/parametertemplates/view.ts';

class ParameterViewManager {
    private readonly host: ParameterViewHost;
    private readonly state: ParameterViewManagerOptions['parameterState'];
    private readonly filters: ParameterViewFilters = {
        search: '',
        group: null,
        view: 'all'
    };
    private icons: Record<string, TrustedHtml> = {};
    private model: ModelRecord | null = null;
    private virtualModel = false;
    private readonly elementCache: ParameterElementCache = new Map();
    private readonly eventDisposers: Array<() => void> = [];
    private readonly boundEvents: BoundParameterEvents = new Map();
    private readonly fieldStateTracker: FieldStateTracker;
    private readonly rail: ParameterCategoryRailController;
    constructor({ host, parameterState }: ParameterViewManagerOptions) {
        if (!host) {
            throw new Error('ParameterViewManager requires a host');
        }
        this.host = host;
        this.state = parameterState;
        this.rail = new ParameterCategoryRailController(host);
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
        this.fieldStateTracker.clearAll();
        this.clearElementCache();
        this.updateSummary();
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
        this.rail.dispose();
        this.clearElementCache();
        if (this.virtualModel) {
            renderVirtualModel(this.host, container, this.model);
            return;
        }
        if (this.state.count === 0) {
            renderNoParameters(this.host, container, this.getTemplateOptions());
            return;
        }
        renderParameters(this.host, this.state, container, this.getTemplateOptions());
        this.refreshElementCache();
        this.rail.attach(container);
        this.filters.group = readModelDetailParameterGroup(this.host.storage);
        this.rail.setView(this.filters.view);
        this.rail.setGroup(this.filters.group);
        this.refreshModificationState();
        this.applyInvalidHighlights();
        this.applyFilters();
        this.bindParameterControls(container);
    }
    private bindParameterControls(container: Element): void {
        bindParameterControls({
            host: this.host,
            container,
            boundEvents: this.boundEvents,
            eventDisposers: this.eventDisposers,
            onUpdateArrayItemValue: (parameterKey: string, index: number, value: ParameterValue) => this.updateArrayItemValue(parameterKey, index, value),
            onUpdateParameter: (parameterKey: string, value: ParameterValue) => this.updateParameter(parameterKey, value),
            onUpdateJsonParameter: (parameterKey: string, json: string, textareaId: string) => this.updateJsonParameter(parameterKey, json, textareaId),
            onSetParameterValidity: (parameterKey: string, valid: boolean) => this.setParameterValidity(parameterKey, valid)
        });
    }
    disposeEventHandlers(): void {
        disposeEventHandlers(this.eventDisposers, this.boundEvents);
    }
    setSearchFilter(query: string | null): void {
        this.filters.search = normalizeSearchMatchQuery(query);
        this.applyFilters();
    }
    clearSearchFilter(): void {
        this.setSearchFilter('');
    }
    toggleGroup(group: ParameterGroup): void {
        this.filters.group = this.filters.group === group ? null : group;
        persistModelDetailParameterGroup(this.host.storage, this.filters.group);
        this.rail.setGroup(this.filters.group);
        this.applyFilters();
    }
    setView(view: ParameterView): void {
        this.filters.view = view;
        this.rail.setView(view);
        this.applyFilters();
    }
    navigateToCategory(category: string): void {
        this.rail.navigate(category);
    }
    applyFilters(): void {
        const categoryCounts = applyFilters(this.host, this.state, this.filters, this.elementCache, (key: string) => this.hasPendingEdit(key));
        categoryCounts.forEach((count, category) => this.rail.updateCategoryCount(category, count));
        this.rail.scheduleSync();
    }
    applyInvalidHighlights(): void {
        this.fieldStateTracker.reapplyDomState();
    }
    private syncParameterCustomizedState(parameterKey: string): void {
        syncParameterCustomizedState({ host: this.host, state: this.state, resolveElement: (key: string) => this.resolveElement(key) }, parameterKey);
    }
    setParameterModifiedState(parameterKey: string, isModified: boolean): void {
        this.fieldStateTracker.setModified(parameterKey, isModified);
        this.syncRevertButton(parameterKey);
    }
    private hasPendingEdit(parameterKey: string): boolean {
        return this.fieldStateTracker.isModified(parameterKey) || this.fieldStateTracker.isInvalid(parameterKey);
    }
    private syncRevertButton(parameterKey: string): void {
        const item = this.resolveElement(parameterKey);
        const revertButton = item ? this.host.pageDom.optional(PARAMETER_REVERT_SELECTOR, item) : null;
        if (revertButton) {
            this.host.pageDom.toggleClass(revertButton, CSS_CLASSES.HIDDEN, !this.hasPendingEdit(parameterKey));
        }
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
                this.syncParameterCustomizedState(linkedParameterKey);
                this.setParameterModifiedState(linkedParameterKey, this.state.isParameterModified(linkedParameterKey));
                this.handleModificationStateChange();
            }
        }
    }
    refreshModificationState(): void {
        refreshModificationState(
            this.state,
            (key: string, isModified: boolean) => {
                this.syncParameterCustomizedState(key);
                this.setParameterModifiedState(key, isModified);
            },
            () => this.handleModificationStateChange()
        );
        if (this.filters.view !== 'all') {
            this.applyFilters();
        }
    }
    handleModificationStateChange(): void {
        this.updateSummary();
        this.host.notifySaveChanged();
    }
    private updateSummary(): void {
        const keys = this.state.getParameterKeys();
        const unsavedCount = keys.filter((key) => this.hasPendingEdit(key)).length;
        this.rail.updateViewCounts({
            all: keys.length,
            customized: keys.filter((key) => this.state.isParameterCustomized(key)).length,
            unsaved: unsavedCount
        });
        PARAMETER_GROUPS.forEach((group) => this.rail.updateGroupCount(group, keys.filter((key) => this.state.getMetadata(key)?.group === group).length));
        this.host.updateUnsavedParametersBadge(unsavedCount);
    }
    setParameterValidity(parameterKey: string, valid: boolean): void {
        this.fieldStateTracker.setInvalid(parameterKey, valid ? null : 'invalid');
        this.syncRevertButton(parameterKey);
        this.handleModificationStateChange();
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
            this.host.pageDom.toggleClass(validation, 'error', true);
            this.setParameterValidity(parameterKey, false);
            return;
        }
        this.setParameterValidity(parameterKey, true);
        this.updateParameter(parameterKey, parsed);
        this.host.pageDom.updateText(validation, '');
        this.host.pageDom.toggleClass(validation, 'error', false);
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
        this.syncParameterCustomizedState(parameterKey);
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
        const container = nextWrapper.closest('.parameters-content');
        if (!container) {
            throw new Error('Parameters container missing after array rerender');
        }
        this.disposeEventHandlers();
        this.refreshElementCache();
        this.bindParameterControls(container);
    }
    updateParameterUI(parameterKey: string, value: ParameterValue): void {
        updateParameterUi(this.host, this.state, parameterKey, value, (key: string) => this.rerenderArrayInput(key));
    }
    resetParameter(parameterKey: string): void {
        this.setParameterValidity(parameterKey, true);
        const validation = this.host.pageDom.optional(`${resolveParameterInputId(parameterKey)}-validation`);
        if (validation) {
            this.host.pageDom.updateText(validation, '');
            this.host.pageDom.toggleClass(validation, 'error', false);
        }
        resetParameterValue({
            state: this.state,
            parameterKey,
            updateParameterUI: (key: string, value: ParameterValue) => this.updateParameterUI(key, value),
            syncParameterCustomizedState: (key: string) => this.syncParameterCustomizedState(key),
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
        this.rail.dispose();
        this.clearElementCache();
        this.model = null;
    }
}
export { ParameterViewManager };
export type { ParameterViewHost, ParameterViewManagerOptions };

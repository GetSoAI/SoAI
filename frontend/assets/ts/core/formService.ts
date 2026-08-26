/* SoAI - Shared frontend form service [frontend/assets/ts/core/formService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { setControlValidity } from '@core/dom/formValidity.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isFunction, isHTMLElement, isInstanceOf, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

if (!isFunction(ResourceTracker)) {
    throw new Error('ResourceTracker must load before FormService');
}

interface ChangeData {
    element: HTMLElement;
    path: string;
    value: JsonValue | undefined;
    hasChanges: boolean;
    valid: boolean;
}

type ChangeHandler = (data: ChangeData) => void;

const SETTINGS_VALIDITY_OWNER_SELECTOR = '.setting-item';

const isFormControlValueValid = (element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): boolean => {
    if (isInstanceOf(element, HTMLInputElement) && element.type === 'number') {
        return element.validity.valid;
    }
    return true;
};

interface ConfigurationManager {
    updateValue: (path: string, value: JsonValue) => void;
    hasChanges: boolean;
}

class FormManager {
    container: HTMLElement;
    changeHandlers: Set<ChangeHandler>;
    resources: ResourceTracker;

    constructor(container: HTMLElement) {
        this.container = container;
        this.changeHandlers = new Set();
        this.resources = new ResourceTracker();
    }

    queryUI(selector: string, context: HTMLElement | null = null): Element[] {
        return dom.resolveAll(selector, context || this.container);
    }

    bindToConfiguration(configManager: ConfigurationManager): () => void {
        if (!configManager) {
            throw new Error('Configuration manager is required');
        }

        this.setupFormListeners(configManager);
        return () => this.cleanup();
    }

    setupFormListeners(configManager: ConfigurationManager): void {
        this.queryUI('input, textarea, select').forEach((element) => {
            if (!(isInstanceOf(element, HTMLInputElement) || isInstanceOf(element, HTMLTextAreaElement) || isInstanceOf(element, HTMLSelectElement))) {
                return;
            }
            const htmlElement = element;
            const handleChange = (): void => {
                const path = dom.getData(htmlElement, 'path');
                if (!path) return;

                if (isInstanceOf(htmlElement, HTMLInputElement) && htmlElement.type === 'checkbox') {
                    updateToggleLabel(htmlElement);
                }

                if (!isFormControlValueValid(htmlElement)) {
                    setControlValidity(htmlElement, false, SETTINGS_VALIDITY_OWNER_SELECTOR);
                    this.notifyChange({ element: htmlElement, path, value: undefined, hasChanges: configManager.hasChanges, valid: false });
                    return;
                }

                let value: JsonValue;
                try {
                    value = this.extractElementValue(htmlElement);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler?.warn?.('FormService', 'Failed to read form value', runtimeError);
                    setControlValidity(htmlElement, false, SETTINGS_VALIDITY_OWNER_SELECTOR);
                    this.notifyChange({ element: htmlElement, path, value: undefined, hasChanges: configManager.hasChanges, valid: false });
                    return;
                }
                if (!isJsonValue(value)) {
                    throw new Error('Form configuration value must be JSON-compatible');
                }
                configManager.updateValue(path, value);
                setControlValidity(htmlElement, true, SETTINGS_VALIDITY_OWNER_SELECTOR);
                this.notifyChange({ element: htmlElement, path, value, hasChanges: configManager.hasChanges, valid: true });
            };

            const isCheckboxOrRadio = isInstanceOf(htmlElement, HTMLInputElement) && (htmlElement.type === 'checkbox' || htmlElement.type === 'radio');
            if (isCheckboxOrRadio) {
                this.resources.addEventListener(htmlElement, 'change', handleChange);
            } else {
                this.resources.addEventListener(htmlElement, 'input', handleChange);
                this.resources.addEventListener(htmlElement, 'change', handleChange);
            }
        });
    }

    extractElementValue(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): JsonValue {
        if (isInstanceOf(element, HTMLInputElement) && element.type === 'checkbox') {
            return element.checked;
        }
        if (dom.hasClass(element, 'setting-json')) {
            try {
                return parseRequiredJsonText(element.value);
            } catch (error) {
                const message = error instanceof SyntaxError ? error.message : 'Invalid JSON';
                throw new Error(`Invalid JSON value: ${message}`);
            }
        }
        if (isInstanceOf(element, HTMLInputElement) && element.type === 'number') {
            const number = readFiniteInputValueOrNull(element);
            if (number === null) {
                throw new Error('Invalid number value');
            }
            return number;
        }
        return element.value;
    }

    onChange(handler: ChangeHandler): () => void {
        if (!isFunction(handler)) {
            throw new Error('Handler must be a function');
        }
        this.changeHandlers.add(handler);
        return () => this.changeHandlers.delete(handler);
    }

    notifyChange(data: ChangeData): void {
        this.changeHandlers.forEach((handler) => handler(data));
    }

    cleanup(): void {
        this.resources?.cleanup();
        this.changeHandlers.clear();
    }
}

class FormService {
    initialized: boolean;
    managers: Map<string, FormManager>;

    constructor() {
        this.initialized = false;
        this.managers = new Map();
    }

    createManager(containerSelector: string | HTMLElement): FormManager {
        const resolved = isString(containerSelector) ? dom.resolve(containerSelector.startsWith('#') ? containerSelector : `#${containerSelector}`) : containerSelector;

        if (!resolved) {
            throw new Error(`Form container not found: ${containerSelector}`);
        }
        if (!isHTMLElement(resolved)) {
            throw new Error('Form container must be an HTMLElement');
        }
        const container = resolved;

        const managerId = isString(containerSelector) ? containerSelector : container.id || generateSecureId({ prefix: 'manager', separator: '_' });

        const manager = new FormManager(container);
        this.managers.set(managerId, manager);
        return manager;
    }

    getManager(managerId: string): FormManager | undefined {
        return this.managers.get(managerId);
    }

    destroyManager(managerId: string): void {
        const manager = this.managers.get(managerId);
        if (manager) {
            manager.cleanup();
            this.managers.delete(managerId);
        }
    }

    destroyAllManagers(): void {
        this.managers.forEach((manager) => {
            manager.cleanup();
        });
        this.managers.clear();
    }

    getManagerCount(): number {
        return this.managers.size;
    }
}

let formServiceInstance: FormService | null = null;

const getFormService = (): FormService => {
    if (formServiceInstance === null) {
        formServiceInstance = new FormService();
    }
    return formServiceInstance;
};

const createFormManager = (containerSelector: string | HTMLElement): FormManager => getFormService().createManager(containerSelector);

const getFormManager = (managerId: string): FormManager | undefined => getFormService().getManager(managerId);

const destroyFormManager = (managerId: string): void => {
    getFormService().destroyManager(managerId);
};

export { FormManager, FormService, createFormManager, destroyFormManager, getFormManager, getFormService };

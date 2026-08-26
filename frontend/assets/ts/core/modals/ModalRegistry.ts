/* SoAI - Standardized modal registry with a fixed enterprise-grade contract [frontend/assets/ts/core/modals/ModalRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { resolveModalLayoutContract } from '@core/modals/layoutPresets.ts';
import type { ModalConfig, ModalRegisterOptions } from '@core/modals/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const STANDARD_MODAL_BEHAVIOR: Readonly<Omit<ModalConfig, 'size' | 'minWidth' | 'minHeight' | 'onOpen' | 'onClose'>> = Object.freeze({
    closeOnEsc: true,
    closeOnOverlay: true,
    restoreFocus: true,
    resizable: true,
    dynamic: true,
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    defaultWidth: null,
    defaultHeight: null,
    maxWidth: null,
    maxHeight: null,
    allowFullscreen: true
});

const normalizeOptionalBoolean = (value: boolean | undefined, fallback: boolean, label: string): boolean => {
    if (value === undefined) {
        return fallback;
    }
    if (typeof value === 'boolean') {
        return value;
    }
    throw new TypeError(`Modal ${label} option must be a boolean (found "${String(value)}")`);
};

const normalizeLifecycle = (options: ModalRegisterOptions): { onOpen: ModalConfig['onOpen']; onClose: ModalConfig['onClose'] } => {
    const onOpen = options.onOpen === null ? null : isFunction(options.onOpen) ? options.onOpen : null;
    const onClose = options.onClose === null ? null : isFunction(options.onClose) ? options.onClose : null;
    return { onOpen, onClose };
};

const normalizeInitialFocusSelector = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error('Modal initialFocusSelector must be a non-empty selector string');
    }
    return trimmed;
};

class ModalRegistry {
    readonly #configs: Map<string, ModalConfig>;

    constructor() {
        this.#configs = new Map();
    }

    register(id: string, options: ModalRegisterOptions): ModalConfig {
        if (!isObject(options)) {
            throw new TypeError(`Modal "${id}" registration options must be an object`);
        }
        if (this.#configs.has(id)) {
            throw new Error(`Modal "${id}" is already registered`);
        }

        const contract = resolveModalLayoutContract(options.layout);
        const lifecycle = normalizeLifecycle(options);
        const initialFocusSelector = normalizeInitialFocusSelector(options.initialFocusSelector);

        const config: ModalConfig = {
            ...STANDARD_MODAL_BEHAVIOR,
            ...contract,
            resizable: normalizeOptionalBoolean(options.resizable, STANDARD_MODAL_BEHAVIOR.resizable, 'resizable'),
            allowFullscreen: normalizeOptionalBoolean(options.allowFullscreen, STANDARD_MODAL_BEHAVIOR.allowFullscreen, 'allowFullscreen'),
            initialFocusSelector,
            onOpen: lifecycle.onOpen,
            onClose: lifecycle.onClose
        };

        this.#configs.set(id, config);
        return config;
    }

    getConfig(id: string): ModalConfig {
        const config = this.#configs.get(id);
        if (!config) {
            throw new Error(`Modal "${id}" is not registered`);
        }
        return config;
    }
}

export { ModalRegistry };

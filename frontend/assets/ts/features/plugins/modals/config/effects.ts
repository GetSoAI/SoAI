/* SoAI - Plugin configuration modal effects [frontend/assets/ts/features/plugins/modals/config/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { parseConfigFieldValue, readConfigFieldMetadata } from '@features/plugins/modals/config/service.ts';
import type { ConfigManagerHost, ConfigurationManager } from '@features/plugins/modals/config/types.ts';

interface BindPluginConfigInputListenersContext {
    host: ConfigManagerHost;
    form: HTMLElement;
    manager: ConfigurationManager;
    onFieldValueChanged: (key: string) => void;
    onFieldValidationChanged: (key: string, message: string | null, validationId: string | null) => void;
}

const setPluginConfigFieldValidationMessage = (host: ConfigManagerHost, validationId: string | null, message: string | null, context: Element): void => {
    if (!validationId) {
        return;
    }
    const validation = host.optionalHTMLElement(validationId, context);
    if (!validation) {
        return;
    }
    host.updateText(validation, message ?? '');
    host.toggleClassName(validation, 'error', Boolean(message));
};

const clearPluginConfigFormIfPresent = (host: ConfigManagerHost, modalId: string, modalRoot: HTMLElement): void => {
    const form = host.optionalHTMLElement(modalUiSelector(modalId, 'form'), modalRoot);
    if (!form) {
        return;
    }
    form.replaceChildren();
};

const bindPluginConfigInputListeners = (context: BindPluginConfigInputListenersContext): Array<() => void> => {
    const handleConfigInput = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
            return;
        }

        const metadata = readConfigFieldMetadata(target);
        if (!metadata) {
            return;
        }

        let parseErrorMessage: string | null = null;
        let value: JsonValue = '';
        try {
            value = parseConfigFieldValue(target, metadata);
        } catch (error) {
            const runtimeError = ensureError(error);
            parseErrorMessage = runtimeError.message;
        }
        if (parseErrorMessage !== null) {
            setPluginConfigFieldValidationMessage(context.host, metadata.validationId, parseErrorMessage, context.form);
            context.onFieldValidationChanged(metadata.key, parseErrorMessage, metadata.validationId);
            return;
        }
        setPluginConfigFieldValidationMessage(context.host, metadata.validationId, null, context.form);
        context.onFieldValidationChanged(metadata.key, null, metadata.validationId);
        context.manager.updateValue(metadata.key, value);
        context.onFieldValueChanged(metadata.key);
    };

    return [context.host.on(context.form, 'input', handleConfigInput), context.host.on(context.form, 'change', handleConfigInput)];
};

const disposeConfigDisposers = (disposers: Array<() => void>, warningMessage: string): Array<() => void> => {
    if (!disposers.length) {
        return [];
    }

    for (const dispose of disposers) {
        try {
            dispose();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('ConfigManager', warningMessage, runtimeError);
        }
    }

    return [];
};

const disposeConfigDisposer = (disposer: (() => void) | null, warningMessage: string): null => {
    if (!disposer) {
        return null;
    }

    try {
        disposer();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ConfigManager', warningMessage, runtimeError);
    }

    return null;
};

const focusFirstPluginConfigField = (host: ConfigManagerHost, form: HTMLElement): void => {
    const field = host.optionalHTMLElement('.config-field', form);
    if (field instanceof HTMLElement) {
        field.focus({ preventScroll: true });
    }
};

export { bindPluginConfigInputListeners, clearPluginConfigFormIfPresent, disposeConfigDisposer, disposeConfigDisposers, focusFirstPluginConfigField };

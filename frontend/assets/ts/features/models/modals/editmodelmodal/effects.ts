/* SoAI - Models feature edit model modal effects [frontend/assets/ts/features/models/modals/editmodelmodal/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement } from '@core/dom/typedElements.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { canDeleteModelRecord } from '@core/models/modelDeletionEligibility.ts';
import { resolveModelPluginName, resolveModelSourceName } from '@core/models/modelIdentity.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { renderOpenAICapabilityOverrides } from '@features/models/capabilities/openaiCapabilityRendering.ts';
import type { OpenAICapabilityOverrideState } from '@features/models/capabilities/openaiCapabilityState.ts';
import type { EditModelModalHost } from '@features/models/modals/editmodelmodal/types.ts';

const resolveEditModelPlugin = (host: EditModelModalHost, model: ModelRecord) => {
    const pluginName = resolveModelPluginName(model);
    return pluginName ? host.operations.findPluginRecord(pluginName) : null;
};

const updateEditModelDeleteVisibility = (host: EditModelModalHost, model: ModelRecord, modalRoot: HTMLElement): void => {
    const deleteButton = requireButtonElement(host.view, modalUiSelector(modalRoot.id, 'delete-model'), 'EditModelModalManager delete button', modalRoot);
    host.view.toggleClassName(deleteButton, 'u-hidden', !canDeleteModelRecord(model, resolveEditModelPlugin(host, model)), modalRoot);
};

const populateEditModelCapabilities = (host: EditModelModalHost, model: ModelRecord, state: OpenAICapabilityOverrideState, modalRoot: HTMLElement): void => {
    const container = host.view.requireHTMLElement(modalUiSelector(modalRoot.id, 'capabilities'), modalRoot);
    const field = host.view.requireHTMLElement(modalUiSelector(modalRoot.id, 'capabilities-field'), modalRoot);
    const source = model.openaiCapabilities;
    if (!isObject(source) || isArray(source)) {
        host.view.updateHTML(container, '');
        host.view.toggleClassName(container, 'u-hidden', true, modalRoot);
        host.view.toggleClassName(field, 'u-hidden', true, modalRoot);
        return;
    }
    const html = renderOpenAICapabilityOverrides({
        model,
        plugin: resolveEditModelPlugin(host, model),
        manifest: host.operations.getCapabilityManifest(),
        state,
        host: {
            resolveOpenAICapabilityLabel: (category, token) => host.operations.resolveOpenAICapabilityLabel(category, token)
        }
    });
    const trustedHtml = toTrustedUiHtml(html);
    host.view.updateHTML(container, trustedHtml);
    host.view.toggleClassName(field, 'u-hidden', false, modalRoot);
    host.view.toggleClassName(container, 'u-hidden', false, modalRoot);
};

const clearEditModelModal = (host: EditModelModalHost, modalRoot: HTMLElement): void => {
    const sourceName = host.view.optionalHTMLElement(modalUiSelector(modalRoot.id, 'source-model-id'), modalRoot);
    const enabledField = host.view.optionalHTMLElement(modalUiSelector(modalRoot.id, 'enabled-field'), modalRoot);
    const enabledState = host.view.optionalHTMLElement(modalUiSelector(modalRoot.id, 'enabled-state'), modalRoot);
    const capabilitiesField = host.view.optionalHTMLElement(modalUiSelector(modalRoot.id, 'capabilities-field'), modalRoot);
    const capabilities = host.view.optionalHTMLElement(modalUiSelector(modalRoot.id, 'capabilities'), modalRoot);
    if (sourceName) {
        host.view.updateText(sourceName, '');
    }
    if (capabilities) {
        host.view.updateHTML(capabilities, '');
        host.view.toggleClassName(capabilities, 'u-hidden', true, modalRoot);
    }
    if (enabledState) {
        host.view.updateText(enabledState, '');
    }
    if (enabledField) {
        host.view.toggleClassName(enabledField, 'u-hidden', true, modalRoot);
    }
    if (capabilitiesField) {
        host.view.toggleClassName(capabilitiesField, 'u-hidden', true, modalRoot);
    }
};

const showCopyNotification = (host: EditModelModalHost, message: string, type: NotificationType, successMessage: string): void => {
    if (type === 'copy') {
        host.view.showNotification(successMessage, 'copy');
        return;
    }
    host.view.showNotification(message, type);
};

const copyEditModelSourceName = async (host: EditModelModalHost, model: ModelRecord): Promise<void> => {
    if (!host.operations.getClipboardService().isSupported()) {
        host.view.showNotification(i18n.t('common.clipboard.copyUnavailable'), 'warning');
        return;
    }
    const sourceName = resolveModelSourceName(model);
    if (!sourceName) {
        throw new Error('EditModelModalManager copy requires a source model identifier');
    }
    const successMessage = i18n.t('models.modal.edit.copyNameSuccess');
    await host.operations.copyToClipboard(sourceName, {
        notify: (message: string, type: NotificationType): void => {
            showCopyNotification(host, message, type, successMessage);
        }
    });
};

export { clearEditModelModal, copyEditModelSourceName, populateEditModelCapabilities, updateEditModelDeleteVisibility };

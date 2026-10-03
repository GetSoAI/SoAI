/* SoAI - Plugin package drop validation and binding [frontend/assets/ts/features/plugins/modals/downloadmanager/pluginPackageDrop.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { isNode } from '@core/typeGuards.ts';
import { bindFileDropArea, transferHasSingleFileMatching } from '@core/ui/fileDropArea.ts';
import type { DownloadManagerHost } from '@features/plugins/modals/downloadmanager/contracts.ts';

const PLUGIN_PACKAGE_EXTENSION = '.soaiplugin';

interface PluginPackageDropBinding {
    host: DownloadManagerHost;
    modalId: string;
    signal: AbortSignal;
    onFileSelected(event: Event): void;
}

const isPluginPackageFile = (file: File): boolean => file.name.toLowerCase().endsWith(PLUGIN_PACKAGE_EXTENSION);

const requirePluginPackageDropArea = (host: DownloadManagerHost, modalId: string): HTMLButtonElement => {
    const modalRoot = host.view.modals.requireElement(modalId);
    const dropArea = host.view.requireHTMLElement(modalUiSelector(modalId, 'file-drop-area'), modalRoot);
    if (!(dropArea instanceof HTMLButtonElement)) {
        throw new TypeError('Plugin download modal file drop area must be a button');
    }
    return dropArea;
};

const dropAreaAcceptsPluginPackage = (dropArea: HTMLButtonElement, event: DragEvent): boolean => {
    return !dropArea.disabled && transferHasSingleFileMatching(event, isPluginPackageFile);
};

const canAcceptPluginPackageDrop = (host: DownloadManagerHost, modalId: string, event: DragEvent): boolean => {
    const dropArea = requirePluginPackageDropArea(host, modalId);
    return dropAreaAcceptsPluginPackage(dropArea, event);
};

const isAcceptedPluginPackageDrop = (host: DownloadManagerHost, modalId: string, event: DragEvent): boolean => {
    const target = event.target;
    const dropArea = requirePluginPackageDropArea(host, modalId);
    if (!isNode(target) || !dropAreaAcceptsPluginPackage(dropArea, event)) {
        return false;
    }
    return dropArea.contains(target);
};

const bindPluginPackageDropArea = (binding: PluginPackageDropBinding): void => {
    const modalRoot = binding.host.view.modals.requireElement(binding.modalId);
    const dropArea = requirePluginPackageDropArea(binding.host, binding.modalId);
    bindFileDropArea({
        element: dropArea,
        signal: binding.signal,
        isEnabled: () => !dropArea.disabled,
        acceptsDrop: (event) => dropAreaAcceptsPluginPackage(dropArea, event),
        onFilesRejected: () => {
            binding.host.session.showNotification(i18n.t('plugins.modal.addPlugin.fileHelp'), 'warning');
        },
        onFilesDropped: (files, event): void => {
            const file = files.length === 1 ? files[0] : undefined;
            if (file === undefined || !isPluginPackageFile(file) || event.dataTransfer === null) {
                throw new Error('Accepted plugin file drop must contain one .soaiplugin file');
            }
            const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
            const input = requireInputElement(resolver, modalUiSelector(binding.modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot);
            input.files = event.dataTransfer.files;
            binding.onFileSelected(event);
        },
        setTimer: binding.host.timing.setTimer,
        clearTimer: binding.host.timing.clearTimer
    });
};

export { bindPluginPackageDropArea, canAcceptPluginPackageDrop, isAcceptedPluginPackageDrop, isPluginPackageFile };

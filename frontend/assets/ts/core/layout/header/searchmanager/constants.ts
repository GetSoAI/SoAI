/* SoAI - Shared layout search manager constants [frontend/assets/ts/core/layout/header/searchmanager/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

export const ICON_ALIASES: Record<string, IconName> = Object.freeze({
    config: 'config',
    configuration: 'config',
    devices: 'device',
    device: 'device',
    models: 'model-default',
    model: 'model-default',
    virtual: 'model-default',
    pages: 'file-generic',
    page: 'file-generic',
    files: 'file-generic',
    conversations: 'chat',
    conversation: 'chat',
    prompts: 'prompt',
    prompt: 'prompt',
    help: 'help',
    modal: 'settings',
    modals: 'settings',
    'power-actions': 'power',
    poweractions: 'power',
    plugins: 'plugin',
    plugin: 'plugin',
    devicenetwork: 'device-network',
    devicestorage: 'device-storage'
});

export const SEARCH_TEMPLATES: Record<string, string> = Object.freeze({
    searching: '<div class="search-loading">{message}</div>',
    preparing: '<div class="search-no-results"><div class="search-no-results-text">{message}</div></div>',
    noResults: '<div class="search-no-results"><div class="search-no-results-text">{message}</div></div>',
    searchError: '<div class="search-error"><div class="search-error-text">{message}</div></div>'
});

/* SoAI - Startup recovery translation contract [frontend/assets/ts/core/languageservice/bootMessageCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TranslationKey } from '@core/i18n/index.ts';

const BOOT_MESSAGE_KEYS = ['app.errors.initFailed', 'app.errors.unknown', 'app.errors.editionIntegrity.title', 'app.errors.editionIntegrity.message', 'app.errors.discoveryHelp.heading', 'app.errors.discoveryHelp.items.backendRunning', 'app.errors.discoveryHelp.items.discoveryReachable', 'app.errors.discoveryHelp.items.noFirewall', 'app.errors.discoveryHelp.defaultPorts', 'common.actions.reloadPage', 'detached.errors.initFailed', 'app.detachedWindow.errors.noPageSpecified', 'app.detachedWindow.errors.initializationFailed'] satisfies readonly TranslationKey[];

type BootMessageKey = (typeof BOOT_MESSAGE_KEYS)[number];
interface BootMessageLocale {
    code: string;
    direction: 'ltr' | 'rtl';
    messages: Record<string, string>;
}
interface BootMessageCatalog {
    defaultLanguage: string;
    locales: BootMessageLocale[];
}

export { BOOT_MESSAGE_KEYS };
export type { BootMessageKey, BootMessageCatalog };

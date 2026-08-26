/* SoAI - Settings section render lifecycle helper [frontend/assets/ts/core/settings/settingsSectionRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';

type SettingsSectionFilterMode = 'always' | 'when-search' | 'never';

interface SettingsSectionRuntimeOptions {
    container: Element | null;
    render: () => TrustedHtml;
    renderMarkup: (container: Element, markup: TrustedHtml) => void;
    bind: () => void;
    filter: () => void;
    hasSearchQuery?: (() => boolean) | undefined;
    afterRender?: ((container: Element) => void) | undefined;
    filterMode?: SettingsSectionFilterMode | undefined;
}

const shouldFilterSettingsSection = (options: SettingsSectionRuntimeOptions): boolean => {
    const mode = options.filterMode ?? 'when-search';
    if (mode === 'always') {
        return true;
    }
    if (mode === 'never') {
        return false;
    }
    return options.hasSearchQuery?.() === true;
};

const renderSettingsSection = (options: SettingsSectionRuntimeOptions): boolean => {
    const container = options.container;
    if (container === null) {
        return false;
    }
    options.renderMarkup(container, options.render());
    options.afterRender?.(container);
    options.bind();
    if (shouldFilterSettingsSection(options)) {
        options.filter();
    }
    return true;
};

export { renderSettingsSection };
export type { SettingsSectionFilterMode, SettingsSectionRuntimeOptions };

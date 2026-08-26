/* SoAI - Shared layout sidebar rendering [frontend/assets/ts/core/layout/sidebar/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ElementOptions } from '@core/dom/types.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { MAIN_STATE_SERVICE_ID } from '@core/indicators/protocols.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface SidebarConfigEntry {
    type: 'separator' | 'page' | 'component';
    id?: string | undefined;
    component?: string | undefined;
    section?: string | undefined;
    icon?: IconName | null | undefined;
    label?: string | undefined;
    getLabel?: (() => string) | null | undefined;
    actions?: readonly string[] | undefined;
}

interface SidebarConfigEntryCandidate {
    type?: SidebarConfigEntry['type'] | undefined;
    id?: string | null | undefined;
    component?: string | null | undefined;
    section?: string | null | undefined;
    icon?: IconName | null | undefined;
    label?: string | null | undefined;
    getLabel?: (() => string) | null | undefined;
    actions?: readonly string[] | undefined;
}

interface SidebarComponentInstance {
    initialize?: (() => HTMLElement | Promise<HTMLElement>) | undefined;
    setCollapsed?: ((collapsed: boolean) => void) | undefined;
}

type DomInstance = typeof dom;

interface SidebarViewHost {
    getMenuElement: () => HTMLElement | null;
    resolveLabel: (cfg: SidebarConfigEntry) => string;
    resolveIconMarkup: (icon: IconName | null | undefined) => Promise<TrustedHtml>;
    waitForComponent: (name: string | null) => Promise<SidebarComponentInstance>;
    updateMainStateIndicator: () => void;
}

class SidebarRenderer {
    readonly #sidebar: SidebarViewHost;
    readonly #dom: DomInstance;

    constructor(sidebar: SidebarViewHost, domApi: DomInstance) {
        this.#sidebar = sidebar;
        this.#dom = domApi;
    }

    async render(entries: SidebarConfigEntry[]): Promise<void> {
        const menu = this.#sidebar.getMenuElement();
        if (!menu) {
            errorHandler.warn('Sidebar', 'Sidebar menu element unavailable');
            return;
        }
        const fragment = this.#dom.createFragment();
        for (const entry of entries) {
            try {
                const node = await this.build(entry);
                if (node) {
                    this.#dom.appendChild(fragment, node);
                } else {
                    errorHandler.warn('Sidebar', 'Sidebar entry rendering returned null', { entry });
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.error('Sidebar', 'Sidebar entry rendering failed', { entry, error: runtimeError });
                if (entry.type === 'component') {
                    throw runtimeError;
                }
            }
        }
        this.#dom.replaceContent(menu, '');
        this.#dom.appendChild(menu, fragment);
    }

    async build(entry: SidebarConfigEntry): Promise<HTMLElement | null> {
        if (!entry) return null;
        if (entry.type === 'separator') return this.#dom.create('li', { className: 'sidebar-separator' });

        const li = this.#createListItem(entry);
        if (entry.type === 'component') {
            const componentName = entry.component;
            const component = await this.#sidebar.waitForComponent(componentName ?? null);
            if (!isFunction(component.initialize)) {
                throw new Error(`Sidebar component "${componentName ?? '<unknown>'}" must expose initialize()`);
            }
            try {
                const element = await Promise.resolve(component.initialize());
                if (!(element instanceof HTMLElement)) {
                    throw new Error(`Sidebar component "${componentName ?? '<unknown>'}" initialize() must return an HTMLElement`);
                }
                this.#dom.appendChild(li, element);
                if (entry.component === MAIN_STATE_SERVICE_ID) {
                    this.#sidebar.updateMainStateIndicator();
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.error('Sidebar', 'Sidebar component initialization failed', {
                    component: componentName,
                    error: runtimeError
                });
                throw runtimeError;
            }
            return li;
        }

        if (entry.type !== 'page') {
            errorHandler.warn('Sidebar', 'Sidebar entry type is not supported', { entry });
            return null;
        }

        const entryId = isString(entry.id) ? entry.id.trim() : '';
        if (!entryId) {
            errorHandler.warn('Sidebar', 'Sidebar page entry missing id', { entry });
            return null;
        }
        const label = this.#sidebar.resolveLabel(entry);
        const link = this.#dom.create('a', {
            href: `#${entryId}`,
            className: 'sidebar-link',
            dataset: { page: entryId },
            'aria-label': label
        });
        setTooltipText(link, label);
        const btn = this.#dom.create('span', {
            className: 'ui-icon-button sidebar-icon-button'
        });
        this.#dom.setHTML(btn, await this.#sidebar.resolveIconMarkup(entry.icon), { escape: false });
        const text = this.#dom.create('span', { className: 'sidebar-label' });
        this.#dom.setText(text, label);
        this.#dom.appendChild(link, [btn, text]);
        this.#dom.appendChild(li, link);
        return li;
    }

    #createListItem(entry: SidebarConfigEntry): HTMLElement {
        const options: ElementOptions = {};
        const entryId = isString(entry.id) ? entry.id : '';
        const sectionId = isString(entry.section) ? entry.section : '';
        if (entryId || sectionId) {
            const dataset: Record<string, string> = {};
            if (entryId) dataset['entry'] = entryId;
            if (sectionId) dataset['section'] = sectionId;
            options['dataset'] = dataset;
        }
        return this.#dom.create('li', options);
    }
}

const isSidebarConfigEntry = (value: SidebarConfigEntryCandidate | null | undefined): value is SidebarConfigEntry => {
    if (!isObject(value)) return false;
    if (!('type' in value)) return false;
    const typeValue = value.type;
    return typeValue === 'separator' || typeValue === 'page' || typeValue === 'component';
};

const requireSidebarConfigEntries = (value: readonly SidebarConfigEntryCandidate[] | null | undefined, label: string): SidebarConfigEntry[] => {
    if (!(value instanceof Array)) {
        throw new TypeError(`${label} must be an array`);
    }
    const out: SidebarConfigEntry[] = [];
    for (const entry of value) {
        if (!isSidebarConfigEntry(entry)) {
            throw new TypeError(`${label} must contain SidebarConfigEntry objects`);
        }
        out.push(entry);
    }
    return out;
};

export { SidebarRenderer, requireSidebarConfigEntries };
export type { SidebarComponentInstance, SidebarConfigEntry, SidebarViewHost };

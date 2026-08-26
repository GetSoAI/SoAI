/* SoAI - Settings page control layer theme manager controller [frontend/assets/ts/pages/settings/controllers/thememanager/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { canAccessUiSurface, createAccessContextFromAuth, createAccessRequirement } from '@core/access/accessPolicy.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { getSidebarNavigationBlueprint } from '@core/routeregistry/service.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { UI_IDS, type StorageService } from '@features/settings/public.ts';
import type { AddThemeManagerCleanup, CustomizationType, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';

interface ThemeCustomizationControllerDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    dashboardProductTitle: () => (() => string) | null;
}

interface CustomizationItem {
    id: string;
    getLabel: () => string;
    disabled?: boolean;
}

class ThemeCustomizationController {
    readonly #host: ThemeManagerHost;
    readonly #addCleanup: AddThemeManagerCleanup;
    readonly #dashboardProductTitle: () => (() => string) | null;

    constructor({ host, addCleanup, dashboardProductTitle }: ThemeCustomizationControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
        this.#dashboardProductTitle = dashboardProductTitle;
    }

    setupCustomizationSection(type: CustomizationType): void {
        const config = this.#getCustomizationConfig(type);

        const button = narrowButton(this.#host.pageDom.requireHTMLElement(config.btnId), `Customization button "${config.btnId}"`);

        button.classList.add('ui-variant-warning');
        this.#addCleanup(
            this.#host.pageResources.on(button, 'click', () => {
                if (button.classList.contains('ui-variant-accent')) {
                    this.#saveCustomizationChanges(config, button);
                    return;
                }
                this.#enterCustomizationEditMode(config, button);
            })
        );
    }

    #getCustomizationConfig(type: CustomizationType): {
        type: CustomizationType;
        btnId: string;
        containerId: string;
        dataAttr: string;
        storageGet: (storage: StorageService) => string[];
        storageSet: (storage: StorageService, ids: string[]) => void;
        getItems: () => CustomizationItem[];
        disabledCheck: (item: CustomizationItem) => boolean;
    } {
        switch (type) {
            case 'sidebar':
                return {
                    type,
                    btnId: UI_IDS.SIDEBAR_EDIT_BTN,
                    containerId: UI_IDS.SIDEBAR_CHECKBOXES_CONTAINER,
                    dataAttr: 'page-id',
                    storageGet: (storage: StorageService) => storage.getHiddenSidebarPages(),
                    storageSet: (storage: StorageService, ids: string[]) => storage.setHiddenSidebarPages(ids),
                    getItems: () => {
                        const accessContext = createAccessContextFromAuth(getAuthManager());
                        return getSidebarNavigationBlueprint()
                            .filter((entry) => canAccessUiSurface(createAccessRequirement({ authenticated: true, admin: entry.adminOnly }), accessContext))
                            .map((entry) => {
                                if (!entry.getLabel) {
                                    throw new Error(`Sidebar item "${entry.id}" is missing getLabel`);
                                }
                                return { id: entry.id, getLabel: entry.getLabel };
                            });
                    },
                    disabledCheck: (item) => item.id === 'dashboard'
                };
            case 'dashboard':
                return {
                    type,
                    btnId: UI_IDS.DASHBOARD_EDIT_BTN,
                    containerId: UI_IDS.DASHBOARD_CHECKBOXES_CONTAINER,
                    dataAttr: 'element-id',
                    storageGet: (storage: StorageService) => storage.getHiddenDashboardElements(),
                    storageSet: (storage: StorageService, ids: string[]) => storage.setHiddenDashboardElements(ids),
                    getItems: () => {
                        const dashboardTitle = this.#dashboardProductTitle();
                        return [
                            { id: 'status', getLabel: () => i18n.t('dashboard.sections.status.title'), disabled: true },
                            ...(dashboardTitle ? [{ id: 'productCapabilities', getLabel: dashboardTitle }] : []),
                            { id: 'logs', getLabel: () => i18n.t('dashboard.sections.logs.title') },
                            { id: 'plugins', getLabel: () => i18n.t('dashboard.sections.plugins.title') },
                            { id: 'models', getLabel: () => i18n.t('dashboard.sections.models.title') },
                            { id: 'hardwareWidgets', getLabel: () => i18n.t('dashboard.sections.hardwareWidgets.title') },
                            { id: 'network', getLabel: () => i18n.t('dashboard.sections.network.title') },
                            { id: 'imagecard', getLabel: () => i18n.t('dashboard.sections.imagecard.title') },
                            { id: 'memo', getLabel: () => i18n.t('dashboard.sections.memo.title') },
                            { id: 'requests', getLabel: () => i18n.t('dashboard.sections.requests.title') },
                            { id: 'clock', getLabel: () => i18n.t('dashboard.sections.clock.title') },
                            { id: 'throughput', getLabel: () => i18n.t('dashboard.sections.throughput.title') },
                            { id: 'quickActions', getLabel: () => i18n.t('dashboard.sections.quickActions.title') }
                        ];
                    },
                    disabledCheck: (item) => item.disabled === true
                };
            default:
                throw new Error(`Unknown customization type "${type}"`);
        }
    }

    #enterCustomizationEditMode(
        config: {
            type: CustomizationType;
            btnId: string;
            containerId: string;
            dataAttr: string;
            storageGet: (storage: StorageService) => string[];
            storageSet: (storage: StorageService, ids: string[]) => void;
            getItems: () => CustomizationItem[];
            disabledCheck: (item: CustomizationItem) => boolean;
        },
        button: HTMLButtonElement
    ): void {
        const storage = this.#host.storage;
        this.#host.pageDom.updateText(button, this.#getSaveLabel(config.type));
        button.classList.remove('ui-variant-warning');
        button.classList.add('ui-variant-accent');

        const container = this.#host.pageDom.requireHTMLElement(config.containerId);
        const hiddenItems = config.storageGet(storage);
        const items = config.getItems();

        const itemsHtml = items
            .map((item) => {
                const isChecked = !hiddenItems.includes(item.id);
                const disabled = config.disabledCheck(item);
                return `<div class="sidebar-page-item"><label class="toggle-switch"><input type="checkbox" data-${config.dataAttr}="${item.id}"${isChecked ? ' checked' : ''}${renderControlDisabledAttributes(disabled)}><span class="slider"></span><span class="toggle-label">${item.getLabel()}</span></label></div>`;
            })
            .join('');

        this.#host.pageDom.updateHtml(container, toTrustedUiHtml(itemsHtml));
        container.classList.remove('sidebar-page-list--hidden');
    }

    #saveCustomizationChanges(
        config: {
            type: CustomizationType;
            btnId: string;
            containerId: string;
            dataAttr: string;
            storageGet: (storage: StorageService) => string[];
            storageSet: (storage: StorageService, ids: string[]) => void;
            getItems: () => CustomizationItem[];
            disabledCheck: (item: CustomizationItem) => boolean;
        },
        button: HTMLButtonElement
    ): void {
        const storage = this.#host.storage;
        const container = this.#host.pageDom.requireHTMLElement(config.containerId);

        const checkboxes = dom.resolveAll(`input[type="checkbox"][data-${config.dataAttr}]`, container).filter((element): element is HTMLInputElement => element instanceof HTMLInputElement);

        const hiddenIds = checkboxes.filter((checkbox) => !checkbox.checked && !checkbox.disabled).map((checkbox) => requireTrimmedDataAttribute(checkbox, config.dataAttr, 'Customization checkbox'));

        config.storageSet(storage, hiddenIds);

        this.#host.pageDom.updateText(button, this.#getEditLabel(config.type));
        button.classList.remove('ui-variant-accent');
        button.classList.add('ui-variant-warning');
        container.classList.add('sidebar-page-list--hidden');
    }

    #getEditLabel(type: CustomizationType): string {
        if (type === 'sidebar') {
            return i18n.t('settings.sidebar.customization.edit');
        }
        return i18n.t('settings.dashboard.customization.edit');
    }

    #getSaveLabel(type: CustomizationType): string {
        if (type === 'sidebar') {
            return i18n.t('settings.sidebar.customization.save');
        }
        return i18n.t('settings.dashboard.customization.save');
    }
}

export { ThemeCustomizationController };

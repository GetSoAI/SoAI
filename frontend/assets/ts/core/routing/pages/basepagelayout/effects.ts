/* SoAI - Shared routing base page layout effects [frontend/assets/ts/core/routing/pages/basepagelayout/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindowOpen } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { PageActionsMenuManager } from '@core/pageActionsMenu.ts';
import { resolveActiveSection } from '@core/pageTransitions.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isBoolean, isFiniteNumber, isFunction, isHTMLElement, isString } from '@core/typeGuards.ts';
import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';

interface HeaderActionMenuCallbacks {
    getBreakpoint?: () => number | null | undefined;
    getSidebarState?: () => boolean | null | undefined;
    onCollapsedChange?: (collapsed: boolean) => void;
    collapseToFit?: boolean;
}

interface HeaderActionMenuHost {
    container: Element | null;
    on: (target: EventTarget, event: string, listener: EventListener, options?: AddEventListenerOptions) => () => void;
    resolveHostContainer(): HTMLElement;
    showNotification: (message: string, type: 'info' | 'warning' | 'error' | 'success', duration?: number) => void;
    pageContext: {
        sanitizer: {
            url: (url: string, options: { allowRelative: boolean; allowDataImage: boolean; allowBlob: boolean }) => string | null;
        };
    };
}

const isTruthyBoolean = (value: boolean | null | undefined): value is boolean => isBoolean(value);

const syncPrefixedSelectLabel = (select: HTMLSelectElement): void => {
    const label = dom.resolve('.dropdown-select__selection-label', select.parentElement);
    const selectedOption = select.selectedOptions.item(0);
    const selectionLabel = selectedOption?.dataset['selectionLabel']?.trim() ?? '';
    if (!(label instanceof HTMLElement) || !selectionLabel) return;
    label.textContent = selectionLabel;
};

const bindPrefixedHeaderSelects = (host: HeaderActionMenuHost, state: BasePageLayoutState): void => {
    if (state.prefixedSelectObserver) return;
    const root = host.resolveHostContainer();
    const selects = dom.resolveAll('select[data-selection-prefix]', root).filter((select): select is HTMLSelectElement => select instanceof HTMLSelectElement);
    if (!selects.length) return;
    selects.forEach((select) => {
        syncPrefixedSelectLabel(select);
        host.on(select, 'change', () => syncPrefixedSelectLabel(select));
    });
    const observer = new MutationObserver(() => selects.forEach(syncPrefixedSelectLabel));
    selects.forEach((select) => observer.observe(select, { attributes: true, subtree: true, attributeFilter: ['selected'] }));
    state.prefixedSelectObserver = observer;
};

const bindHeaderActionMenu = (host: HeaderActionMenuHost, state: BasePageLayoutState, callbacks: HeaderActionMenuCallbacks = {}): void => {
    if (state.pageActionsMenu || !isHTMLElement(host.container)) return;

    const options: {
        host: HeaderActionMenuHost;
        breakpoint?: number;
        sidebarStateProvider?: () => boolean;
        onCollapsedChange?: (collapsed: boolean) => void;
        collapseToFit?: boolean;
    } = { host };

    if (callbacks.collapseToFit === true) {
        options.collapseToFit = true;
    }

    const getBreakpoint = callbacks.getBreakpoint;
    if (isFunction(getBreakpoint)) {
        const breakpointValue = getBreakpoint();
        if (isFiniteNumber(breakpointValue) && breakpointValue > 0) {
            options.breakpoint = breakpointValue;
        }
    }

    const getSidebarState = callbacks.getSidebarState;
    if (isFunction(getSidebarState)) {
        options.sidebarStateProvider = (): boolean => {
            const sidebarStateValue = getSidebarState();
            return isTruthyBoolean(sidebarStateValue) && sidebarStateValue;
        };
    }

    const onCollapsedChange = callbacks.onCollapsedChange;
    if (isFunction(onCollapsedChange)) {
        options.onCollapsedChange = (collapsed: boolean): void => {
            onCollapsedChange(collapsed);
        };
    }

    const pageActionsMenu = new PageActionsMenuManager(options);
    if (!pageActionsMenu.initialize(host.resolveHostContainer())) {
        pageActionsMenu.dispose();
        return;
    }
    state.pageActionsMenu = pageActionsMenu;
};

const attachExternalLinkConfirmation = (host: HeaderActionMenuHost, state: BasePageLayoutState): void => {
    if (state.ctaLinkDisposer) return;
    const hostContainer = host.resolveHostContainer();
    if (!isHTMLElement(hostContainer)) {
        throw err('Host container required for external link confirmations');
    }
    const eventRoot = resolveActiveSection(hostContainer);
    if (!isHTMLElement(eventRoot)) {
        throw err('Mounted page section required for external link confirmations');
    }
    state.externalLinkTargets = null;
    state.ctaLinkDisposer = host.on(eventRoot, 'click', async (event: Event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const link = target.closest('.external-link-confirmation');
        if (!(link instanceof HTMLElement) || !eventRoot.contains(link)) {
            return;
        }
        event.preventDefault();
        const dataset = link.dataset ?? {};
        const datasetHref = isString(dataset['href']) ? dataset['href'] : null;
        const anchorHref = link instanceof HTMLAnchorElement ? link.href : link.getAttribute('href');
        const rawUrl = datasetHref || (isString(anchorHref) ? anchorHref : null) || link.getAttribute('href');
        if (!rawUrl || rawUrl === '#') return;

        const resolvedUrl = host.pageContext.sanitizer.url(rawUrl, {
            allowRelative: false,
            allowDataImage: false,
            allowBlob: false
        });
        if (!resolvedUrl) {
            host.showNotification(i18n.t('ui.errors.invalidUrl'), 'error', 6000);
            return;
        }

        const isChatScopedLink = Boolean(link.closest("[data-section='chat']"));
        const dialogsService = requireDialogsService();
        const showLinkModal = isChatScopedLink ? dialogsService.showChatExternalLinkModal : dialogsService.showExternalLinkModal;
        const linkType = isString(dataset['externalLinkType']) ? dataset['externalLinkType'] : null;
        const title = (() => {
            if (isChatScopedLink) return i18n.t('chat.confirmations.externalLink');
            if (linkType === 'about-website' || linkType === 'about-documentation') return i18n.t('about.confirmations.externalLink');
            if (linkType === 'help-website') return i18n.t('help.confirmations.externalLink');
            return i18n.t('plugins.confirmations.externalLink');
        })();
        const confirmText = (() => {
            if (isChatScopedLink) {
                if (linkType === 'chat-path') {
                    return i18n.t('chat.confirmations.externalPathConfirm');
                }
                return i18n.t('chat.confirmations.externalLinkConfirm');
            }
            if (linkType === 'about-website' || linkType === 'about-documentation') return i18n.t('about.confirmations.externalLinkConfirm');
            if (linkType === 'help-website') return i18n.t('help.confirmations.externalLinkConfirm');
            return i18n.t('plugins.confirmations.externalLinkConfirm');
        })();
        const cancelText = (() => {
            if (isChatScopedLink) return i18n.t('chat.confirmations.externalLinkCancel');
            if (linkType === 'about-website' || linkType === 'about-documentation') return i18n.t('about.confirmations.externalLinkCancel');
            if (linkType === 'help-website') return i18n.t('help.confirmations.externalLinkCancel');
            return i18n.t('plugins.confirmations.externalLinkCancel');
        })();
        const message = (() => {
            if (isChatScopedLink) return i18n.t('chat.confirmations.externalLinkMessage');
            if (linkType === 'plugins-docs-cta') return i18n.t('plugins.confirmations.externalLinkMessageCta');
            if (linkType === 'about-website' || linkType === 'about-documentation') return i18n.t('about.confirmations.externalLinkMessage');
            if (linkType === 'help-website') return i18n.t('help.confirmations.externalLinkMessage');
            return i18n.t('plugins.confirmations.externalLinkMessage');
        })();

        if (
            await showLinkModal({
                title,
                message,
                confirmText,
                cancelText,
                url: resolvedUrl,
                variant: 'info',
                icon: 'external-link'
            })
        ) {
            getWindowOpen()(resolvedUrl, '_blank', 'noopener,noreferrer');
        }
    });
};

const updatePageActionsMenuState = (state: BasePageLayoutState): void => {
    state.pageActionsMenu?.updateDropdownState();
};

export { attachExternalLinkConfirmation, bindHeaderActionMenu, bindPrefixedHeaderSelects, isFiniteNumber, updatePageActionsMenuState, type HeaderActionMenuCallbacks, type HeaderActionMenuHost };

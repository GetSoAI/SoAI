/* SoAI - Shared background tasks effects [frontend/assets/ts/core/backgroundtasks/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import { PAGE_CLASS_PREFIX, SOLID_BACKGROUND_STYLE_ID, WALLPAPER_STYLE_ID } from '@core/backgroundtasks/constants.ts';
import { getCspNonce } from '@core/security/cspNonce.ts';

const resolveStyleElement = (selector: string): HTMLStyleElement | null => {
    const element = dom.resolve(selector);
    return element instanceof HTMLStyleElement ? element : null;
};

const requireBody = (): HTMLElement => {
    const body = dom.resolve('body');
    if (!isHTMLElement(body)) {
        throw new Error('Document body is unavailable');
    }
    return body;
};

const requireHead = (): HTMLElement => {
    const head = dom.resolve('head');
    if (!isHTMLElement(head)) {
        throw new Error('Document head is unavailable');
    }
    return head;
};

const requireMainContainer = (): HTMLElement => {
    const container = dom.resolve('#main-content');
    if (!isHTMLElement(container)) {
        throw new Error('Main content container is unavailable');
    }
    return container;
};

const clearBackgroundClasses = (body: HTMLElement): void => {
    dom.removeClass(body, 'has-wallpaper');
    dom.removeClass(body, 'wallpaper-ready');
    dom.removeClass(body, 'has-solid-background');
    dom.removeClass(body, 'solid-background-ready');
};

const updateBodyRouteClass = (body: HTMLElement, route: string): void => {
    const toRemove: string[] = [];
    const classes = dom.getClasses(body);
    classes.forEach((cls: string) => {
        if (cls.startsWith(PAGE_CLASS_PREFIX)) {
            toRemove.push(cls);
        }
    });
    toRemove.forEach((cls) => dom.removeClass(body, cls));

    if (route) {
        dom.addClass(body, `${PAGE_CLASS_PREFIX}${route}`);
    }
};

const applyWallpaperCSS = (url: string): void => {
    const stylesheetId = `#${WALLPAPER_STYLE_ID}`;
    let styleElement: HTMLStyleElement | null = resolveStyleElement(stylesheetId);
    const nonce = getCspNonce();

    if (styleElement && nonce && styleElement.nonce !== nonce) {
        styleElement.remove();
        styleElement = null;
    }

    if (!styleElement) {
        const created = dom.create('style', {
            id: WALLPAPER_STYLE_ID
        });
        if (!(created instanceof HTMLStyleElement)) {
            throw new Error('Wallpaper style element must be an HTMLStyleElement');
        }
        if (nonce) {
            created.nonce = nonce;
        }
        styleElement = created;
        dom.appendChild(requireHead(), created);
    }

    if (styleElement.dataset['appliedUrl'] === url) {
        return;
    }

    const escapedUrl = url.replace(/'/g, "\\'");
    styleElement.textContent = `
            body.has-wallpaper::before {
                background-image: url('${escapedUrl}');
            }
        `;
    styleElement.dataset['appliedUrl'] = url;
};

const applyWallpaperOverlay = (overlay: number): void => {
    const body = requireBody();
    const opacity = overlay / 100;
    body.style.setProperty('--wallpaper-overlay-opacity', String(opacity));
};

const applySolidBackgroundCSS = (color: string): void => {
    let styleElement: HTMLStyleElement | null = resolveStyleElement(`#${SOLID_BACKGROUND_STYLE_ID}`);
    const nonce = getCspNonce();

    if (styleElement && nonce && styleElement.nonce !== nonce) {
        styleElement.remove();
        styleElement = null;
    }

    if (!styleElement) {
        const created = dom.create('style', {
            id: SOLID_BACKGROUND_STYLE_ID
        });
        if (!(created instanceof HTMLStyleElement)) {
            throw new Error('Solid background style element must be an HTMLStyleElement');
        }
        if (nonce) {
            created.nonce = nonce;
        }
        styleElement = created;
        dom.appendChild(requireHead(), created);
    }

    styleElement.textContent = `
            body.has-solid-background::before {
                background-color: ${color};
            }
        `;
    styleElement.dataset['appliedUrl'] = color;
};

const removeWallpaperStyles = (): void => {
    const wallpaperStyle = resolveStyleElement(`#${WALLPAPER_STYLE_ID}`);
    if (wallpaperStyle) {
        wallpaperStyle.remove();
    }

    const solidBgStyle = resolveStyleElement(`#${SOLID_BACKGROUND_STYLE_ID}`);
    if (solidBgStyle) {
        solidBgStyle.remove();
    }
};

const getBody = (): HTMLElement => requireBody();
const getHead = (): HTMLElement => requireHead();
const getMainContainer = (): HTMLElement => requireMainContainer();
export { applySolidBackgroundCSS, applyWallpaperCSS, applyWallpaperOverlay, clearBackgroundClasses, getBody, getHead, getMainContainer, removeWallpaperStyles, requireBody, requireMainContainer, requireHead, updateBodyRouteClass };

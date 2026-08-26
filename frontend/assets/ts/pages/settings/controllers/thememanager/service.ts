/* SoAI - Settings page theme manager service [frontend/assets/ts/pages/settings/controllers/thememanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { parseFirstPositiveCssPixelValue } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { readFiniteInputValueOrNull, readTrimmedInputValue } from '@core/dom/formValues.ts';
import { narrowButton, narrowInput } from '@core/dom/narrowElement.ts';
import { getComputedStyleStrict, getWindow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import { securityApi } from '@core/security/public.ts';

import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setLoadingButtonState } from '@core/ui/loadingbuttons/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { AddThemeManagerCleanup, RunDetachedWithBoundary, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { refreshWallpaperPreview } from '@pages/settings/controllers/thememanager/effects.ts';
import { requireUiPrefsWallpaperOverlay } from '@pages/settings/controllers/uiprefs/guards.ts';

interface ThemeWallpaperControllerDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    runDetachedWithBoundary: RunDetachedWithBoundary;
    isMounted: () => boolean;
}

class ThemeWallpaperController {
    readonly #host: ThemeManagerHost;
    readonly #addCleanup: AddThemeManagerCleanup;
    readonly #runDetachedWithBoundary: RunDetachedWithBoundary;
    readonly #isMounted: () => boolean;
    readonly #wallpaperRefreshToken = new SequenceToken();
    #wallpaperDownloadInFlight = false;

    constructor({ host, addCleanup, runDetachedWithBoundary, isMounted }: ThemeWallpaperControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
        this.#runDetachedWithBoundary = runDetachedWithBoundary;
        this.#isMounted = isMounted;
    }

    setupEventListeners(): void {
        const uploadButton = narrowButton(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_UPLOAD), 'Wallpaper upload button');
        const fileInput = narrowInput(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_FILE), 'Wallpaper file input');
        const urlInput = narrowInput(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_URL), 'Wallpaper url input');
        const downloadButton = narrowButton(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_DOWNLOAD), 'Wallpaper download button');
        const overlaySlider = narrowInput(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_OVERLAY_SLIDER), 'Wallpaper overlay slider');
        const overlayValue = this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_OVERLAY_VALUE);

        if (fileInput.type !== 'file') {
            throw new TypeError('Wallpaper file input must be type="file"');
        }
        if (overlaySlider.type !== 'range') {
            throw new TypeError('Wallpaper overlay slider must be type="range"');
        }
        this.#syncDownloadButtonVisibility(urlInput, downloadButton);
        this.#syncWallpaperPreviewHeight();
        this.#addCleanup(
            this.#host.pageResources.on(uploadButton, 'click', () => {
                if (this.#host.getCurrentWallpaperUrl() !== null) {
                    this.#runDetachedWithBoundary('settings:theme:deleteWallpaper', async () => {
                        await this.#deleteWallpaper();
                    });
                    return;
                }
                fileInput.click();
            })
        );
        this.#addCleanup(this.#host.pageResources.on(getWindow(), 'resize', () => this.#syncWallpaperPreviewHeight()));
        this.#addCleanup(this.#host.pageResources.on(getWindow(), INTERFACE_SCALE_CHANGED_EVENT, () => this.#syncWallpaperPreviewHeight()));
        this.#addCleanup(
            this.#host.pageResources.on(fileInput, 'change', () => {
                const file = fileInput.files?.[0];
                if (!file) {
                    return;
                }
                this.#runDetachedWithBoundary('settings:theme:uploadWallpaper', async () => {
                    try {
                        await this.#uploadWallpaper(file);
                    } finally {
                        fileInput.value = '';
                    }
                });
            })
        );

        const downloadFromUrl = async (): Promise<void> => {
            if (this.#wallpaperDownloadInFlight) {
                return;
            }
            const url = this.#readDownloadWallpaperUrl(urlInput);
            if (url === null) {
                this.#syncDownloadButtonVisibility(urlInput, downloadButton);
                return;
            }
            await this.#downloadWallpaper(url);
        };

        this.#addCleanup(
            this.#host.pageResources.on(downloadButton, 'click', () => {
                this.#runDetachedWithBoundary('settings:theme:downloadWallpaper', async () => {
                    await downloadFromUrl();
                });
            })
        );
        this.#addCleanup(this.#host.pageResources.on(urlInput, 'input', () => this.#syncDownloadButtonVisibility(urlInput, downloadButton)));
        this.#addCleanup(
            this.#host.pageResources.on(urlInput, 'keypress', (event: Event) => {
                if (!(event instanceof KeyboardEvent)) {
                    return;
                }
                if (event.key === 'Enter') {
                    this.#runDetachedWithBoundary('settings:theme:downloadWallpaper', async () => {
                        await downloadFromUrl();
                    });
                }
            })
        );

        const initialOverlay = requireUiPrefsWallpaperOverlay(this.#host.getUiPrefValue('wallpaperOverlay'));
        overlaySlider.value = String(initialOverlay);
        this.#host.pageDom.updateText(overlayValue, `${initialOverlay}%`);
        this.#host.applyWallpaperOverlay(String(initialOverlay));

        this.#addCleanup(
            this.#host.pageResources.on(overlaySlider, 'input', () => {
                const safe = readFiniteInputValueOrNull(overlaySlider) ?? 0;
                const value = normalizeProgressPercent(safe) ?? 0;
                this.#host.setUiPrefValue('wallpaperOverlay', value);
                this.#host.pageDom.updateText(overlayValue, `${value}%`);
                this.#host.applyWallpaperOverlay(String(value));
            })
        );
    }

    async reload(): Promise<void> {
        try {
            await this.#refreshWallpaperPreview();
        } catch (error) {
            this.#host.feedback.handle(ensureError(error), 'Theme wallpaper reload');
            this.#host.feedback.show(i18n.t('settings.notifications.wallpaperReloadFailed'), 'error');
        }
    }

    dispose(): void {
        this.#wallpaperRefreshToken.invalidate();
    }

    #setWallpaperButtonLoading(isLoading: boolean): HTMLButtonElement {
        const button = narrowButton(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_UPLOAD), 'Wallpaper upload button');
        setLoadingButtonState(dom, button, isLoading);
        if (!isLoading) {
            setTooltipText(button, button.getAttribute('aria-label') ?? button.textContent?.trim() ?? '');
        }
        return button;
    }

    async #uploadWallpaper(file: File): Promise<void> {
        this.#setWallpaperButtonLoading(true);
        try {
            await this.#host.uploadWallpaper(file);
            this.#host.feedback.show(i18n.t('settings.notifications.wallpaperUploadSuccess'), 'success');
            await this.#refreshWallpaperPreview();
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#reportWallpaperOperationError(runtimeError, 'Theme wallpaper upload');
        } finally {
            this.#setWallpaperButtonLoading(false);
        }
    }

    async #downloadWallpaper(url: string): Promise<void> {
        const downloadButton = narrowButton(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_DOWNLOAD), 'Wallpaper download button');
        const urlInput = narrowInput(this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_URL), 'Wallpaper url input');
        this.#wallpaperDownloadInFlight = true;
        setControlDisabledState(downloadButton, true);
        try {
            await this.#host.downloadWallpaper(url);
            this.#host.feedback.show(i18n.t('settings.notifications.wallpaperDownloadSuccess'), 'download');
            urlInput.value = '';
            await this.#refreshWallpaperPreview();
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#reportWallpaperOperationError(runtimeError, 'Theme wallpaper download');
        } finally {
            this.#wallpaperDownloadInFlight = false;
            this.#syncDownloadButtonVisibility(urlInput, downloadButton);
        }
    }

    async #deleteWallpaper(): Promise<void> {
        this.#setWallpaperButtonLoading(true);
        try {
            await this.#host.deleteWallpaper();
            this.#host.feedback.show(i18n.t('settings.notifications.wallpaperDeleteSuccess'), 'success');
            await this.#refreshWallpaperPreview();
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#reportWallpaperOperationError(runtimeError, 'Theme wallpaper delete');
        } finally {
            this.#setWallpaperButtonLoading(false);
        }
    }

    async #refreshWallpaperPreview(): Promise<void> {
        const expectedToken = this.#wallpaperRefreshToken.next();
        await refreshWallpaperPreview({
            host: this.#host,
            isMounted: this.#isMounted,
            expectedToken,
            isTokenActive: (token) => this.#wallpaperRefreshToken.isActive(token)
        });
    }

    #reportWallpaperOperationError(error: Error, context: string): void {
        const runtimeError = ensureError(error);
        this.#host.feedback.handle(runtimeError, context);
        showOperationFailureNotification({
            error: runtimeError,
            fallbackMessage: String(runtimeError),
            rawMessage: true,
            showNotification: (message): void => this.#host.feedback.show(message, 'error')
        });
    }

    #readDownloadWallpaperUrl(input: HTMLInputElement): string | null {
        return securityApi.sanitizeAbsoluteHttpUrl(readTrimmedInputValue(input));
    }

    #syncDownloadButtonVisibility(input: HTMLInputElement, button: HTMLButtonElement): void {
        const isValidUrl = this.#readDownloadWallpaperUrl(input) !== null;
        button.hidden = !isValidUrl;
        setControlDisabledState(button, !isValidUrl || this.#wallpaperDownloadInFlight);
    }

    #syncWallpaperPreviewHeight(): void {
        const preview = this.#host.pageDom.requireHTMLElement('.wallpaper-preview-container');
        const detailsColumn = this.#host.pageDom.requireHTMLElement('.wallpaper-details-column');
        const sampleItem = this.#host.pageDom.requireHTMLElement('.wallpaper-details-column > .setting-item');
        const sampleHeight = measureLayoutBox(sampleItem).height;
        if (!Number.isFinite(sampleHeight) || sampleHeight <= 0) {
            return;
        }
        const detailsStyle = getComputedStyleStrict(detailsColumn);
        const gapPx = parseFirstPositiveCssPixelValue(detailsStyle.rowGap, parseFirstPositiveCssPixelValue(detailsStyle.gap, 0));
        const targetHeightPx = Math.ceil(sampleHeight * 6 + gapPx * 5);
        preview.style.setProperty('--wallpaper-preview-target-height', `${targetHeightPx}px`);
    }
}

export { ThemeWallpaperController };

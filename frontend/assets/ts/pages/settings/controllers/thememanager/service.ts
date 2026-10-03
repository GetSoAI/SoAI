/* SoAI - Settings page theme manager service [frontend/assets/ts/pages/settings/controllers/thememanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { inlineDelta, scrollByInline } from '@core/layout/direction.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { optionalClosestElement, parseFirstPositiveCssPixelValue, requireClosestElement } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { readFiniteInputValueOrNull, readTrimmedInputValue } from '@core/dom/formValues.ts';
import { narrowButton, narrowInput } from '@core/dom/narrowElement.ts';
import { getComputedStyleStrict, getWindow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import { securityApi } from '@core/security/public.ts';
import type { DefaultWallpaperId } from '@core/theme/defaultWallpapers.ts';

import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { OverflowNavController } from '@core/ui/controls/OverflowNav.ts';
import { setLoadingButtonState } from '@core/ui/loadingbuttons/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { commitDefaultWallpaper } from '@pages/settings/controllers/thememanager/backgroundSelection.ts';
import type { AddThemeManagerCleanup, RunDetachedWithBoundary, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { readBuiltInWallpaperOptionId, refreshWallpaperPreview, updateWallpaperUI } from '@pages/settings/controllers/thememanager/effects.ts';
import { setupWallpaperThumbnailLoading } from '@pages/settings/controllers/thememanager/wallpaperThumbnailState.ts';
import { formatWallpaperOverlayValue } from '@pages/settings/controllers/thememanager/mappers.ts';
import { syncSolidBackgroundControl } from '@pages/settings/controllers/thememanager/solidBackgroundController.ts';
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
    readonly #wallpaperRefresh = new LatestRequestController();
    #wallpaperDownloadInFlight = false;
    #defaultSelectionInFlight = false;
    #builtInOverflowNav: OverflowNavController | null = null;

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
        this.#setupBuiltInWallpaperOptions();
        this.#addCleanup(
            this.#host.pageResources.on(uploadButton, 'click', () => {
                if (this.#host.getCurrentWallpaper() !== null) {
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
        this.#host.pageDom.updateText(overlayValue, formatWallpaperOverlayValue(initialOverlay));
        this.#host.applyWallpaperOverlay(String(initialOverlay));

        this.#addCleanup(
            this.#host.pageResources.on(overlaySlider, 'input', () => {
                const safe = readFiniteInputValueOrNull(overlaySlider) ?? 0;
                const value = normalizeProgressPercent(safe) ?? 0;
                this.#host.setUiPrefValue('wallpaperOverlay', value);
                this.#host.pageDom.updateText(overlayValue, formatWallpaperOverlayValue(value));
                this.#host.applyWallpaperOverlay(String(value));
            })
        );
        updateWallpaperUI(this.#host);
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
        this.#wallpaperRefresh.invalidate();
        this.#builtInOverflowNav?.dispose();
        this.#builtInOverflowNav = null;
    }

    #setupBuiltInWallpaperOptions(): void {
        const options = this.#host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_BUILTIN_OPTIONS);
        const carousel = requireClosestElement(options, '.wallpaper-builtin-carousel', 'Built-in wallpaper options');
        const leftButton = this.#host.pageDom.requireHTMLElement('.wallpaper-builtin-nav--left', carousel);
        const rightButton = this.#host.pageDom.requireHTMLElement('.wallpaper-builtin-nav--right', carousel);
        const selected = dom.resolve('.wallpaper-builtin-option[aria-pressed="true"]', options);
        if (selected instanceof HTMLElement) {
            const optionsBox = measureLayoutBox(options);
            const selectedBox = measureLayoutBox(selected);
            const centerDelta = selectedBox.left + selectedBox.width / 2 - optionsBox.left - optionsBox.width / 2;
            scrollByInline(options, inlineDelta(centerDelta, options), 'instant');
        }
        this.#builtInOverflowNav?.dispose();
        this.#builtInOverflowNav = new OverflowNavController(options, leftButton, rightButton);
        this.#builtInOverflowNav.initialize((target, type, listener, listenerOptions) => this.#host.pageResources.on(target, type, listener, listenerOptions));
        setupWallpaperThumbnailLoading(options, this.#host.pageResources, this.#addCleanup);
        this.#addCleanup(
            this.#host.pageResources.on(options, 'click', (event: Event) => {
                const option = event.target instanceof Element ? optionalClosestElement(event.target, '.wallpaper-builtin-option', options) : null;
                if (option === null) {
                    return;
                }
                const id = readBuiltInWallpaperOptionId(option);
                this.#runDetachedWithBoundary('settings:theme:selectDefaultWallpaper', async () => {
                    await this.#selectDefaultWallpaper(id);
                });
            })
        );
    }

    async #selectDefaultWallpaper(id: DefaultWallpaperId | null): Promise<void> {
        if (this.#defaultSelectionInFlight || this.#host.storage.getDefaultWallpaper() === id) {
            return;
        }
        this.#defaultSelectionInFlight = true;
        try {
            if (id !== null && this.#host.getCurrentWallpaper() !== null && !(await this.#deleteWallpaper())) {
                return;
            }
            commitDefaultWallpaper(this.#host, id);
            syncSolidBackgroundControl(this.#host);
            updateWallpaperUI(this.#host);
        } finally {
            this.#defaultSelectionInFlight = false;
        }
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
            if (await this.#runWallpaperMutation(() => this.#host.uploadWallpaper(file), i18n.t('settings.notifications.wallpaperUploadSuccess'), 'success', 'Theme wallpaper upload')) {
                commitDefaultWallpaper(this.#host, null);
                await this.reload();
            }
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
            if (await this.#runWallpaperMutation(() => this.#host.downloadWallpaper(url), i18n.t('settings.notifications.wallpaperDownloadSuccess'), 'download', 'Theme wallpaper download')) {
                urlInput.value = '';
                commitDefaultWallpaper(this.#host, null);
                await this.reload();
            }
        } finally {
            this.#wallpaperDownloadInFlight = false;
            this.#syncDownloadButtonVisibility(urlInput, downloadButton);
        }
    }

    async #deleteWallpaper(): Promise<boolean> {
        this.#setWallpaperButtonLoading(true);
        try {
            const deleted = await this.#runWallpaperMutation(() => this.#host.deleteWallpaper(), i18n.t('settings.notifications.wallpaperDeleteSuccess'), 'success', 'Theme wallpaper delete');
            if (deleted) {
                await this.reload();
            }
            return deleted;
        } finally {
            this.#setWallpaperButtonLoading(false);
        }
    }

    async #runWallpaperMutation<T>(operation: () => Promise<T>, successMessage: string, notificationType: 'success' | 'download', context: string): Promise<boolean> {
        let succeeded = false;
        try {
            await operation();
            succeeded = true;
        } catch (error) {
            this.#reportWallpaperOperationError(ensureError(error), context);
        }
        if (succeeded) {
            this.#host.feedback.show(successMessage, notificationType);
        }
        return succeeded;
    }

    async #refreshWallpaperPreview(): Promise<void> {
        await this.#wallpaperRefresh.runLatest(async (run) => {
            await refreshWallpaperPreview({
                host: this.#host,
                isMounted: this.#isMounted,
                signal: run.signal,
                isCurrent: run.isCurrent
            });
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
        const sampleItem = this.#host.pageDom.requireHTMLElement('.wallpaper-details-column > .wallpaper-upload-state');
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

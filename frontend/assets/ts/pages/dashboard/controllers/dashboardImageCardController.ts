/* SoAI - Dashboard page image card controller [frontend/assets/ts/pages/dashboard/controllers/dashboardImageCardController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMaxFileUploadBytes } from '@core/api/systemLimitsService.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { DASHBOARD_ACTION_IMAGE_DELETE, DASHBOARD_ACTION_IMAGE_TOGGLE_FIT, DASHBOARD_ACTION_IMAGE_UPLOAD } from '@pages/dashboard/actions.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';

export type ImageFitMode = 'contain' | 'cover';

interface DashboardImageCardStorage {
    getDashboardImageCard: () => string | null;
    setDashboardImageCard: (value: string | null) => void;
    getDashboardImageCardFit: () => ImageFitMode;
    setDashboardImageCardFit: (value: ImageFitMode) => void;
}

interface DashboardImageCardControllerDependencies {
    host: DashboardHost;
    storage: DashboardImageCardStorage;
    isDestroyed: () => boolean;
}

class DashboardImageCardController {
    readonly #host: DashboardHost;
    readonly #storage: DashboardImageCardStorage;
    readonly #isDestroyed: () => boolean;
    #uploadSeq = 0;

    constructor(dependencies: DashboardImageCardControllerDependencies) {
        this.#host = dependencies.host;
        this.#storage = dependencies.storage;
        this.#isDestroyed = dependencies.isDestroyed;
    }

    buildControlsMarkup(): TrustedHtml {
        if (!this.#storage.getDashboardImageCard()) {
            return EMPTY_UI_HTML;
        }
        const isContain = this.#storage.getDashboardImageCardFit() === 'contain';
        const fitIcon = getIconSync('fullscreen', { size: 14, strokeWidth: 1.6 });
        const deleteIcon = getIconSync('close', { size: 14, strokeWidth: 1.5 });
        const fitTitle = isContain ? i18n.t('dashboard.sections.imagecard.fill') : i18n.t('dashboard.sections.imagecard.fit');
        const deleteTitle = i18n.t('dashboard.sections.imagecard.delete');

        const btn = (id: string, action: string, title: string, icon: TrustedHtml, variant: string = 'ui-variant-neutral'): TrustedHtml => {
            return uiHtml`<button type="button" class="ui-icon-button ui-icon-button--titlebar ${variant}" id="${uiAttr(id)}" data-action="${uiAttr(action)}" aria-label="${uiAttr(title)}" data-tooltip="${uiAttr(title)}">${renderIconSlot(icon)}</button>`;
        };

        return uiHtml`${btn('imagecard-fit', DASHBOARD_ACTION_IMAGE_TOGGLE_FIT, fitTitle, fitIcon)}${btn('imagecard-delete', DASHBOARD_ACTION_IMAGE_DELETE, deleteTitle, deleteIcon, 'ui-variant-danger')}`;
    }

    triggerUploadDialog(): void {
        const input = this.#host.optionalUI('#imagecard-file-input');
        if (!(input instanceof HTMLInputElement)) {
            return;
        }
        input.click();
    }

    renderSection(): void {
        const content = this.#host.requireUI('imagecard-content');
        const contentElement = narrowHTMLElement(content, 'Dashboard image card content');

        const imageData = this.#storage.getDashboardImageCard();
        const wrapper = this.#host.createElement('div', { className: 'dashboard-imagecard-wrapper' });
        const wrapperElement = narrowHTMLElement(wrapper, 'Dashboard image card wrapper');

        if (imageData) {
            const display = this.#host.createElement('div', { className: 'dashboard-imagecard-display' });
            const displayElement = narrowHTMLElement(display, 'Dashboard image display wrapper');

            const imgElement = this.#host.createElement('img');
            if (!(imgElement instanceof HTMLImageElement)) {
                throw new TypeError('Dashboard image card must render an img element');
            }
            const img = imgElement;
            img.src = imageData;
            const fitMode = this.#storage.getDashboardImageCardFit();
            img.className = fitMode === 'contain' ? 'fit' : 'fill';
            img.alt = i18n.t('dashboard.sections.imagecard.title');
            displayElement.appendChild(img);
            wrapperElement.appendChild(displayElement);
        } else {
            const upload = this.#host.createElement('div', {
                className: 'dashboard-imagecard-upload',
                id: 'imagecard-upload-area',
                'data-action': DASHBOARD_ACTION_IMAGE_UPLOAD
            });
            const uploadElement = narrowHTMLElement(upload, 'Dashboard image upload area');

            const icon = this.#host.createElement('div', { className: 'dashboard-imagecard-upload-icon' });
            const iconElement = narrowHTMLElement(icon, 'Dashboard image upload icon');
            dom.setHTML(iconElement, getIconSync('window', { size: 28, strokeWidth: 1.6 }), { escape: false });

            const text = this.#host.createElement('div', { className: 'dashboard-imagecard-upload-text' }, i18n.t('dashboard.sections.imagecard.upload'));
            const hint = this.#host.createElement('div', { className: 'dashboard-imagecard-upload-hint' }, i18n.t('dashboard.sections.imagecard.uploadHint'));
            const inputElement = this.#host.createElement('input', {
                type: 'file',
                accept: 'image/*',
                className: 'dashboard-imagecard-input',
                id: 'imagecard-file-input',
                'data-action': DASHBOARD_ACTION_IMAGE_UPLOAD
            });
            if (!(inputElement instanceof HTMLInputElement)) {
                throw new TypeError('Dashboard image upload control must be an input element');
            }
            uploadElement.append(iconElement, narrowHTMLElement(text, 'Dashboard image upload text'), narrowHTMLElement(hint, 'Dashboard image upload hint'), inputElement);
            wrapperElement.appendChild(uploadElement);
        }

        this.#host.replaceElementContent(contentElement, wrapperElement, { escape: false });
        this.#host.flushDOMUpdates();
        this.updateControls();
    }

    updateControls(): void {
        const section = this.#host.requireUI('[data-section-id="imagecard"]');
        const controlsContainer = this.#host.requireUI('.section-controls', section);
        const controlsElement = narrowHTMLElement(controlsContainer, 'Dashboard image card controls container');
        this.#host.replaceElementContent(controlsElement, this.buildControlsMarkup(), { escape: false });
        this.#host.flushDOMUpdates();
    }

    handleUpload(input: HTMLInputElement): void {
        const files = input.files;
        if (!files) {
            return;
        }
        const file = files[0];
        if (!file) {
            return;
        }
        input.value = '';
        let maxFileSize = 0;
        try {
            maxFileSize = getMaxFileUploadBytes();
        } catch (error) {
            this.#host.notify(i18n.t('dashboard.sections.imagecard.limitsUnavailable'), 'error');
            throw ensureError(error);
        }
        if (file.size > maxFileSize) {
            this.#host.notify(i18n.t('dashboard.sections.imagecard.fileTooLarge'), 'error');
            return;
        }
        if (!file.type.startsWith('image/')) {
            this.#host.notify(i18n.t('dashboard.sections.imagecard.invalidType'), 'error');
            return;
        }

        const seq = (this.#uploadSeq += 1);
        const reader = new FileReader();
        reader.onload = (event: ProgressEvent<FileReader>): void => {
            if (seq !== this.#uploadSeq) {
                return;
            }
            if (this.#isDestroyed()) {
                return;
            }
            const result = event.target?.result ?? null;
            if (typeof result === 'string') {
                this.#storage.setDashboardImageCard(result);
                this.renderSection();
            }
        };
        reader.readAsDataURL(file);
    }

    handleDelete(): void {
        this.#storage.setDashboardImageCard(null);
        this.renderSection();
    }

    handleToggleFit(): void {
        const current = this.#storage.getDashboardImageCardFit();
        this.#storage.setDashboardImageCardFit(current === 'contain' ? 'cover' : 'contain');
        this.renderSection();
    }
}

export { DashboardImageCardController };
export type { DashboardImageCardStorage, DashboardImageCardControllerDependencies };

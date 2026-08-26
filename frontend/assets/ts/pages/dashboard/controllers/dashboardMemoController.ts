/* SoAI - Dashboard page memo controller [frontend/assets/ts/pages/dashboard/controllers/dashboardMemoController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { normalizeNonBlankStringOrNull } from '@core/storage/normalization.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { DASHBOARD_ACTION_MEMO_CANCEL, DASHBOARD_ACTION_MEMO_EDIT, DASHBOARD_ACTION_MEMO_SAVE } from '@pages/dashboard/actions.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';

interface DashboardMemoStorage {
    getDashboardMemo: () => string | null;
    setDashboardMemo: (value: string | null) => void;
}

interface DashboardMemoControllerDependencies {
    host: DashboardHost;
    storage: DashboardMemoStorage;
    isDestroyed: () => boolean;
}

class DashboardMemoController {
    readonly #host: DashboardHost;
    readonly #storage: DashboardMemoStorage;
    readonly #isDestroyed: () => boolean;
    #save: SaveController | null = null;
    #editing = false;
    #baselineText = '';

    constructor(dependencies: DashboardMemoControllerDependencies) {
        this.#host = dependencies.host;
        this.#storage = dependencies.storage;
        this.#isDestroyed = dependencies.isDestroyed;
    }

    buildControlsMarkup(): TrustedHtml {
        if (this.#editing) {
            const save = this.#buildButton('dashboard-memo-save', DASHBOARD_ACTION_MEMO_SAVE, i18n.t('common.save'), 'save', 'ui-variant-accent');
            const cancel = this.#buildButton('dashboard-memo-cancel', DASHBOARD_ACTION_MEMO_CANCEL, i18n.t('common.cancel'), 'close', 'ui-variant-neutral');
            return uiHtml`${save}${cancel}`;
        }
        return this.#buildButton('dashboard-memo-edit', DASHBOARD_ACTION_MEMO_EDIT, i18n.t('common.edit'), 'edit');
    }

    renderSection(): void {
        if (this.#isDestroyed()) {
            return;
        }
        const content = this.#host.requireUI('memo-content');
        const wrapper = this.#host.createElement('div', { className: 'dashboard-memo-wrapper' });
        if (!(wrapper instanceof HTMLElement)) {
            throw new TypeError('Dashboard memo wrapper must be an HTMLElement');
        }
        if (this.#editing) {
            this.#renderEditor(wrapper);
        } else {
            this.#renderDisplay(wrapper);
        }
        this.#host.replaceElementContent(content, wrapper, { escape: false });
        this.#host.flushDOMUpdates();
        this.updateControls();
        this.#attachSaveController();
        this.#focusEditor();
    }

    updateControls(): void {
        const section = this.#host.requireUI('[data-section-id="memo"]');
        const controlsContainer = this.#host.requireUI('.section-controls', section);
        this.#host.replaceElementContent(controlsContainer, this.buildControlsMarkup(), { escape: false });
        this.#host.flushDOMUpdates();
    }

    startEditing(): void {
        this.#baselineText = this.#storage.getDashboardMemo() ?? '';
        this.#editing = true;
        this.renderSection();
    }

    async requestSave(): Promise<void> {
        const save = this.#save;
        if (!save) {
            return;
        }
        if (!this.#editing) {
            this.#disposeSaveController();
            return;
        }
        await save.requestSave();
        if (!this.#editing) {
            this.#disposeSaveController();
        }
    }

    cancelEditing(): void {
        if (!this.#editing) {
            return;
        }
        this.#editing = false;
        this.#baselineText = this.#storage.getDashboardMemo() ?? '';
        this.#disposeSaveController();
        this.renderSection();
    }

    hasChanges(): boolean {
        if (!this.#editing) {
            return false;
        }
        return normalizeNonBlankStringOrNull(this.#readDraftText()) !== normalizeNonBlankStringOrNull(this.#baselineText);
    }

    destroy(): void {
        this.#editing = false;
        this.#baselineText = this.#storage.getDashboardMemo() ?? '';
        this.#disposeSaveController();
    }

    #renderDisplay(wrapper: HTMLElement): void {
        const text = this.#storage.getDashboardMemo();
        this.#baselineText = text ?? '';
        const display = this.#host.createElement('div', {
            className: text ? 'dashboard-memo-text' : 'dashboard-memo-text dashboard-memo-text--placeholder'
        });
        if (!(display instanceof HTMLElement)) {
            throw new TypeError('Dashboard memo display must be an HTMLElement');
        }
        display.textContent = text ?? i18n.t('dashboard.sections.memo.placeholder');
        wrapper.appendChild(display);
    }

    #renderEditor(wrapper: HTMLElement): void {
        const textarea = this.#host.createElement('textarea', {
            'aria-label': i18n.t('dashboard.sections.memo.title'),
            className: 'dashboard-memo-textarea',
            id: 'dashboard-memo-textarea',
            rows: 5
        });
        if (!(textarea instanceof HTMLTextAreaElement)) {
            throw new TypeError('Dashboard memo editor must be a textarea');
        }
        textarea.value = this.#baselineText;
        wrapper.appendChild(textarea);
    }

    #buildButton(id: string, action: string, label: string, icon: 'close' | 'edit' | 'save', variant = 'ui-variant-neutral'): TrustedHtml {
        const iconMarkup = getIconSync(icon, { size: 14, strokeWidth: 1.6 });
        return uiHtml`<button type="button" class="ui-icon-button ui-icon-button--titlebar ${uiAttr(variant)}" id="${uiAttr(id)}" data-action="${uiAttr(action)}" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}">${renderIconSlot(iconMarkup)}</button>`;
    }

    #ensureSaveController(): SaveController {
        if (this.#save) {
            return this.#save;
        }
        this.#save = createSaveController({
            headerContextId: 'dashboard.memo',
            headerPriority: SAVE_HEADER_PRIORITY_PAGE,
            requestContextLabel: 'Dashboard memo save',
            units: [
                {
                    id: 'dashboard.memo',
                    hasChanges: (): boolean => this.hasChanges(),
                    save: (): void => this.#saveDraft()
                }
            ]
        });
        return this.#save;
    }

    #attachSaveController(): void {
        if (!this.#editing) {
            return;
        }
        const content = this.#host.requireUI('memo-content');
        this.#ensureSaveController().attach({
            resolveSaveButtons: (): readonly HTMLButtonElement[] => {
                const button = this.#host.requireUI('#dashboard-memo-save');
                if (!(button instanceof HTMLButtonElement)) {
                    throw new TypeError('Dashboard memo save control must be a button');
                }
                return [button];
            },
            autoNotifyRoot: content
        });
    }

    #readDraftText(): string {
        const editor = this.#host.requireUI('#dashboard-memo-textarea');
        if (!(editor instanceof HTMLTextAreaElement)) {
            throw new TypeError('Dashboard memo editor must be a textarea');
        }
        return editor.value;
    }

    #focusEditor(): void {
        if (!this.#editing) {
            return;
        }
        const editor = this.#host.requireUI('#dashboard-memo-textarea');
        if (!(editor instanceof HTMLTextAreaElement)) {
            throw new TypeError('Dashboard memo editor must be a textarea');
        }
        editor.focus();
    }

    #saveDraft(): void {
        const normalized = normalizeNonBlankStringOrNull(this.#readDraftText());
        this.#storage.setDashboardMemo(normalized);
        this.#baselineText = normalized ?? '';
        this.#editing = false;
        this.#disposeSaveController();
        this.renderSection();
        this.#host.notify(i18n.t('dashboard.sections.memo.saved'), 'success');
    }

    #disposeSaveController(): void {
        this.#save?.dispose();
        this.#save = null;
    }
}

export { DashboardMemoController };
export type { DashboardMemoControllerDependencies, DashboardMemoStorage };

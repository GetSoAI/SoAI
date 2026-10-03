/* SoAI - SoAI Bench run section DOM ownership [frontend/assets/ts/features/hardware/modals/soaibenchrun/sectionRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, isPresenceExiting, removeWithPresence } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { createOperationProgressReporter } from '@core/operationprogress/public.ts';
import type { OperationProgressData, OperationProgressReporter } from '@core/operationprogress/types.ts';
import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { staticUiHtml } from '@core/security/uiHtml.ts';
import { getBusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { resolveSoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/runPhase.ts';
import { renderSectionActionButton, renderSoAIBenchSection, resolveSectionActions, resolveSectionBadge, resolveSectionStartedLabel, type SoAIBenchSectionAction } from '@features/hardware/modals/soaibenchrun/sectionView.ts';
import type { SoAIBenchRunEntry, SoAIBenchRunModalHost, SoAIBenchRunPhase, SoAIBenchRunsFreshness } from '@features/hardware/modals/soaibenchrun/types.ts';
import { progressDetailsForRun, progressMessageForRun, progressPercentForRun, renderRunReportBody } from '@features/hardware/modals/soaibenchrun/view.ts';
import { getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';

const RUN_PROGRESS_KEY = 'hardware-soaibench-run';

interface SoAIBenchSectionRenderContext {
    historyAvailable: boolean;
    publishing: boolean;
    freshness: SoAIBenchRunsFreshness;
}

type SectionContentMode = 'progress' | 'report';

const materializeElement = (markup: TrustedHtml): HTMLElement => {
    const element = dom.createFragment(markup).firstElementChild;
    if (!(element instanceof HTMLElement)) {
        throw new Error('SoAIBench section markup did not produce an element');
    }
    return element;
};

const requireSlot = (root: HTMLElement, slot: string): HTMLElement => {
    const element = dom.resolve(`[data-soaibench-slot="${slot}"]`, root);
    if (!(element instanceof HTMLElement)) {
        throw new Error(`SoAIBench section slot "${slot}" is missing`);
    }
    return element;
};

const isProgressPhase = (phase: SoAIBenchRunPhase): boolean => phase !== 'terminal' && phase !== 'rejected';

const resolveStatusText = (entry: SoAIBenchRunEntry, phase: SoAIBenchRunPhase, freshness: SoAIBenchRunsFreshness): { text: string; loading: boolean } => {
    if (entry.recovering) {
        return { text: i18n.t('hardware.modals.soaibenchRun.progress.checkingStatus'), loading: true };
    }
    if (phase === 'unresolved') {
        return { text: entry.reason ?? i18n.t('hardware.modals.soaibenchRun.progress.statusUnavailable'), loading: false };
    }
    if (isProgressPhase(phase) && !freshness.live) {
        const age = freshness.updatedAtMs === null ? getSoAIBenchNotAvailableLabel() : formatRelativeTime(freshness.updatedAtMs, Date.now());
        return { text: i18n.t('hardware.modals.soaibenchRun.progress.reconnecting', { age }), loading: true };
    }
    return { text: '', loading: false };
};

class SoAIBenchRunSectionView {
    readonly root: HTMLElement;
    readonly #host: SoAIBenchRunModalHost;
    readonly #heading: HTMLElement;
    readonly #started: HTMLElement;
    readonly #badge: HTMLElement;
    readonly #content: HTMLElement;
    readonly #status: HTMLElement;
    readonly #actions: HTMLElement;
    #mode: SectionContentMode | null = null;
    #reportSignature = '';
    #progressSignature = '';
    #statusSignature = '';
    #reporter: OperationProgressReporter | null = null;

    constructor(host: SoAIBenchRunModalHost, entry: SoAIBenchRunEntry) {
        this.#host = host;
        this.root = materializeElement(renderSoAIBenchSection(entry));
        this.#heading = requireSlot(this.root, 'heading');
        this.#started = requireSlot(this.root, 'started');
        this.#badge = requireSlot(this.root, 'badge');
        this.#content = requireSlot(this.root, 'content');
        this.#status = requireSlot(this.root, 'status');
        this.#actions = requireSlot(this.root, 'actions');
    }

    render(entry: SoAIBenchRunEntry, context: SoAIBenchSectionRenderContext): void {
        const phase = resolveSoAIBenchRunPhase(entry);
        const badge = resolveSectionBadge(entry, phase);
        updateText(this.#started, resolveSectionStartedLabel(entry));
        updateText(this.#badge, badge.label);
        const badgeClassName = `ui-status-badge ${badge.className}`;
        if (this.#badge.className !== badgeClassName) {
            this.#badge.className = badgeClassName;
        }
        if (isProgressPhase(phase)) {
            this.#renderProgress(entry, phase, context.freshness.live);
        } else {
            this.#renderReport(entry);
        }
        const status = resolveStatusText(entry, phase, context.freshness);
        const statusSignature = `${String(status.loading)}:${status.text}`;
        if (statusSignature !== this.#statusSignature) {
            this.#statusSignature = statusSignature;
            renderInlineLoadingStatus(this.#status, status);
        }
        this.#renderActions(entry, resolveSectionActions({ entry, phase, historyAvailable: context.historyAvailable, publishing: context.publishing }));
    }

    focusHeading(): void {
        this.#heading.focus({ preventScroll: true });
    }

    destroy(): void {
        this.#reporter?.destroy();
        this.#reporter = null;
    }

    #renderProgress(entry: SoAIBenchRunEntry, phase: SoAIBenchRunPhase, live: boolean): void {
        if (this.#mode !== 'progress' || this.#reporter === null) {
            this.#host.setHTML(this.#content, staticUiHtml`<div class="hardware-soaibench-progress-host" data-soaibench-slot="progress"></div>`);
            this.#reporter = createOperationProgressReporter(requireSlot(this.#content, 'progress'), { showCancel: false, showBadge: false, extraClassName: 'hardware-soaibench-progress' });
            this.#mode = 'progress';
            this.#reportSignature = '';
            this.#progressSignature = '';
        }
        const stopping = phase === 'stopping';
        const update: OperationProgressData = {
            message: progressMessageForRun(entry.run, stopping),
            details: progressDetailsForRun(entry.run),
            progress: progressPercentForRun(entry.run),
            state: live && phase !== 'unresolved' && !stopping ? 'downloading' : 'pending',
            cancelable: false
        };
        const signature = JSON.stringify(update);
        if (signature !== this.#progressSignature) {
            this.#progressSignature = signature;
            this.#reporter.update(RUN_PROGRESS_KEY, update);
        }
    }

    #renderReport(entry: SoAIBenchRunEntry): void {
        const signature = `${entry.run?.runId ?? ''}:${String(entry.run?.updateSeq ?? -1)}:${entry.reason ?? ''}`;
        if (this.#mode === 'report' && signature === this.#reportSignature) {
            return;
        }
        this.destroy();
        this.#mode = 'report';
        this.#reportSignature = signature;
        this.#progressSignature = '';
        this.#host.setHTML(this.#content, renderRunReportBody(entry.run, entry.reason));
    }

    #renderActions(entry: SoAIBenchRunEntry, actions: readonly SoAIBenchSectionAction[]): void {
        const existing = new Map<string, HTMLButtonElement>();
        for (const child of this.#actions.children) {
            const action = child instanceof HTMLButtonElement ? (child.dataset['action'] ?? '') : '';
            if (child instanceof HTMLButtonElement && action && !existing.has(action)) {
                existing.set(action, child);
            }
        }
        let previous: HTMLButtonElement | null = null;
        for (const action of actions) {
            const button = existing.get(action.action) ?? this.#createActionButton(entry, action);
            existing.delete(action.action);
            this.#updateActionButton(entry, button, action);
            const anchor: Element | null = previous === null ? this.#actions.firstElementChild : previous.nextElementSibling;
            if (button.parentElement !== this.#actions || isPresenceExiting(button)) {
                insertWithPresence(this.#actions, button, anchor);
            }
            if (anchor !== button) {
                this.#actions.insertBefore(button, anchor);
            }
            previous = button;
        }
        for (const stale of existing.values()) {
            const hadFocus = stale.contains(stale.ownerDocument.activeElement);
            removeWithPresence(stale);
            if (hadFocus) {
                this.focusHeading();
            }
        }
    }

    #createActionButton(entry: SoAIBenchRunEntry, action: SoAIBenchSectionAction): HTMLButtonElement {
        const button = materializeElement(renderSectionActionButton(entry, action));
        if (!(button instanceof HTMLButtonElement)) {
            throw new Error('SoAIBench section action markup did not produce a button');
        }
        return button;
    }

    #updateActionButton(entry: SoAIBenchRunEntry, button: HTMLButtonElement, action: SoAIBenchSectionAction): void {
        updateText(button, action.label);
        if (button.getAttribute('aria-label') !== action.ariaLabel) {
            button.setAttribute('aria-label', action.ariaLabel);
            setTooltipText(button, action.ariaLabel);
        }
        if (entry.runId === null) {
            delete button.dataset['runId'];
        } else {
            button.dataset['runId'] = entry.runId;
        }
        if (getBusyDisabledToken(button) === null && button.disabled !== action.disabled) {
            const hadFocus = button === button.ownerDocument.activeElement;
            setControlDisabledState(button, action.disabled);
            if (hadFocus && action.disabled) {
                this.focusHeading();
            }
        }
    }
}

const updateText = (element: HTMLElement, text: string): void => {
    if (element.textContent !== text) {
        element.textContent = text;
    }
};

export { SoAIBenchRunSectionView };

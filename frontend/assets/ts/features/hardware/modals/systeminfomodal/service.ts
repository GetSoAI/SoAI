/* SoAI - Hardware feature system info modal service [frontend/assets/ts/features/hardware/modals/systeminfomodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { decodeHardwareSnapshot } from '@core/api/contracts/hardwareSnapshotContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { parsePluginsCollectionSnapshot } from '@core/plugins/collectionSnapshot.ts';
import { downloadFile } from '@core/primitives/download.ts';
import { HARDWARE, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { requestWebSocketSnapshotArray, requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { formatIsoTimestampForFilename } from '@core/time/localCalendar.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { anonymizeSystemInfoText } from '@features/hardware/privacyAnonymization.ts';
import { HARDWARE_SYSTEM_INFO_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { clearLoadingState, copyAndDownloadButtons, renderLoadingState, requireAnonymizeToggle, requireContentElement, setCopyAndDownloadButtonsDisabled } from '@features/hardware/modals/systeminfomodal/dom.ts';
import { formatSystemInfo } from '@features/hardware/modals/systeminfomodal/mappers.ts';
import { createSystemInfoModalState } from '@features/hardware/modals/systeminfomodal/state.ts';
import type { SystemInfoFormattingInput, SystemInfoModalDependencies, SystemInfoModalHost, SystemInfoModalState } from '@features/hardware/modals/systeminfomodal/types.ts';

class SystemInfoModal {
    readonly modalId = HARDWARE_SYSTEM_INFO_MODAL_ID;
    readonly host: SystemInfoModalHost;
    readonly #openToken = new SequenceToken();
    #state: SystemInfoModalState;

    constructor({ host }: SystemInfoModalDependencies) {
        if (!host) {
            throw new Error('SystemInfoModal requires a host');
        }
        this.host = host;
        this.#state = createSystemInfoModalState();
    }

    handleModalClosed(): void {
        this.#openToken.invalidate();
        this.#state.isOpen = false;
    }

    async open(): Promise<void> {
        return this.host.runWithBoundary('hardware:openSystemInfoModal', async () => {
            const modalRoot = this.host.modals.requireElement(this.modalId);
            const openToken = this.#openToken.next();
            this.#state.isOpen = true;
            const contentElement = requireContentElement(this.host, modalRoot);
            const buttons = copyAndDownloadButtons(this.host, modalRoot);
            const setButtonsDisabled = (isDisabled: boolean): void => setCopyAndDownloadButtonsDisabled(this.host, buttons, isDisabled);

            this.#state.rawSystemInfo = '';
            this.#state.anonymizedSystemInfo = '';
            this.#state.isAnonymized = false;
            this.updateAnonymizeToggleState();
            renderLoadingState(this.host, modalRoot);
            setButtonsDisabled(true);
            this.host.modals.open(this.modalId);

            const [hardwareSnapshot, systemInfoSnapshot, healthSnapshot, pluginsSnapshot] = await Promise.all([requestWebSocketSnapshotRecord(HARDWARE), requestWebSocketSnapshotRecord('system.info'), requestWebSocketSnapshotRecord('system.health'), requestWebSocketSnapshotArray(PLUGINS)]);

            if (!this.#openToken.isActive(openToken)) {
                return;
            }

            const formattedText = this.buildSystemInfoText({
                hardware: decodeHardwareSnapshot(hardwareSnapshot),
                systemInfo: systemInfoSnapshot,
                plugins: parsePluginsCollectionSnapshot(pluginsSnapshot),
                health: healthSnapshot
            });

            clearLoadingState(this.host, contentElement);
            this.host.updateText(contentElement, formattedText);
            this.host.setDataAttribute(contentElement, 'system-info', formattedText);
            this.updateAnonymizeToggleState();
            setButtonsDisabled(false);
        });
    }

    private buildSystemInfoText(data: SystemInfoFormattingInput): string {
        const formatted = formatSystemInfo(data);
        this.#state.rawSystemInfo = formatted;
        this.#state.anonymizedSystemInfo = anonymizeSystemInfoText(formatted);
        this.#state.isAnonymized = false;
        return formatted;
    }

    async copy(): Promise<void> {
        return this.host.runWithBoundary('hardware:copySystemInfo', async () => {
            const modalRoot = this.host.modals.requireElement(this.modalId);
            const contentElement = requireContentElement(this.host, modalRoot);
            if (this.host.domHasClass(contentElement, 'is-loading')) return;
            const text = this.host.getDataAttribute(contentElement, 'system-info') ?? '';
            if (text.length === 0) {
                return this.host.showNotification(i18n.t('hardware.modals.systemInfo.copyUnavailable'), 'error');
            }
            await copyTextWithHostClipboardFeedback(this.host, {
                text,
                successMessage: i18n.t('hardware.modals.systemInfo.copySuccess'),
                unavailableMessage: i18n.t('hardware.modals.systemInfo.copyUnavailable'),
                unavailableType: 'error'
            });
        });
    }

    async download(): Promise<void> {
        return this.host.runWithBoundary('hardware:downloadSystemInfo', async () => {
            const modalRoot = this.host.modals.requireElement(this.modalId);
            const contentElement = requireContentElement(this.host, modalRoot);
            if (this.host.domHasClass(contentElement, 'is-loading')) return;
            const text = this.host.getDataAttribute(contentElement, 'system-info');
            if (!text) return;
            downloadFile(text, `soai-system-info-${formatIsoTimestampForFilename(new Date(), 'seconds')}.txt`, 'text/plain');
            this.host.showNotification(i18n.t('common.notifications.downloadStarted'), 'download');
        });
    }

    handleAnonymizeToggle(event: Event | null): void {
        const checkbox = event?.target;
        if (!(checkbox instanceof HTMLInputElement)) return;
        this.#state.isAnonymized = Boolean(checkbox.checked);
        this.refreshDisplayedContent();
    }

    refreshDisplayedContent(): void {
        const modalRoot = this.host.modals.requireElement(this.modalId);
        const contentElement = requireContentElement(this.host, modalRoot);
        if (this.host.domHasClass(contentElement, 'is-loading')) return;
        if (!this.#state.rawSystemInfo && !this.#state.anonymizedSystemInfo) return;
        const text = this.#state.isAnonymized ? this.#state.anonymizedSystemInfo : this.#state.rawSystemInfo;
        this.host.updateText(contentElement, text);
        this.host.setDataAttribute(contentElement, 'system-info', text);
    }

    updateAnonymizeToggleState(): void {
        const modalRoot = this.host.modals.requireElement(this.modalId);
        const toggle = requireAnonymizeToggle(this.host, modalRoot);
        toggle.checked = this.#state.isAnonymized;
    }
}

export { SystemInfoModal };

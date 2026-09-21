/* SoAI - Hardware feature export actions [frontend/assets/ts/features/hardware/modals/soaibenchrun/exportActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { downloadFile } from '@core/primitives/download.ts';
import { formatIsoTimestampForFilename } from '@core/time/localCalendar.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { buildSoAIBenchRunExportFilename, formatSoAIBenchRunExportText, type SoAIBenchExportRun } from '@features/hardware/modals/soaibenchrun/exportText.ts';
import type { SoAIBenchRunOpenRequest } from '@features/hardware/modals/soaibenchrun/types.ts';

interface SoAIBenchRunExportHost {
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

interface SoAIBenchRunExportActionInput {
    host: SoAIBenchRunExportHost;
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchExportRun;
}

const buildExportPayload = (input: SoAIBenchRunExportActionInput): { text: string; filename: string } => {
    const generatedAt = new Date();
    const text = formatSoAIBenchRunExportText({
        request: input.request,
        run: input.run,
        generatedAt
    });
    const filename = buildSoAIBenchRunExportFilename(input.run, formatIsoTimestampForFilename(generatedAt, 'seconds'));
    return { text, filename };
};

const copySoAIBenchRunExport = async (input: SoAIBenchRunExportActionInput): Promise<void> => {
    const payload = buildExportPayload(input);
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: (value, options) => input.host.copyToClipboard(value, options?.notify ? { notify: options.notify } : undefined),
            hasClipboardSupport: () => input.host.hasClipboardSupport(),
            showNotification: (message, type, duration): void => input.host.showNotification(message, type, duration)
        },
        {
            text: payload.text,
            successMessage: i18n.t('hardware.modals.soaibenchRun.copySuccess'),
            unavailableMessage: i18n.t('hardware.modals.soaibenchRun.copyUnavailable'),
            unavailableType: 'error'
        }
    );
};

const downloadSoAIBenchRunExport = (input: SoAIBenchRunExportActionInput): void => {
    const payload = buildExportPayload(input);
    downloadFile(payload.text, payload.filename, 'text/markdown');
    input.host.showNotification(i18n.t('common.notifications.downloadStarted'), 'download');
};

export { copySoAIBenchRunExport, downloadSoAIBenchRunExport };
export type { SoAIBenchRunExportActionInput };

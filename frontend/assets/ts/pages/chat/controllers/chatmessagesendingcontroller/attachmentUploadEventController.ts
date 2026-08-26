/* SoAI - Event-driven attachment upload handler shared by picker/camera inputs [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/attachmentUploadEventController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveUploadFilesFromEvent } from '@features/chat/public.ts';
import { refreshComposerState } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type AttachmentUploadSource = 'picker' | 'camera' | 'folder';

const handleAttachmentUploadFiles = async (host: MessageSendingHost, files: File[], source: AttachmentUploadSource): Promise<void> => {
    const errorTitle = i18n.t('chat.upload.errorTitle');
    if (files.length === 0) {
        return;
    }
    try {
        await host.services.getAttachmentManager().handleUpload(files, {
            source,
            visionSupported: host.model.isVisionSupportedForCurrentModel()
        });
    } catch (error) {
        const runtimeError = ensureError(error);
        host.platform.handleError(runtimeError, errorTitle, { notify: true });
    }

    refreshComposerState(host, { updateInputState: false });
};

const handleAttachmentUploadFromEvent = async (host: MessageSendingHost, event: Event, source: AttachmentUploadSource): Promise<void> => {
    const errorTitle = i18n.t('chat.upload.errorTitle');
    let files: File[];
    try {
        files = resolveUploadFilesFromEvent(event);
    } catch (error) {
        const runtimeError = ensureError(error);
        host.platform.handleError(runtimeError, errorTitle, { notify: true });
        throw runtimeError;
    }
    await handleAttachmentUploadFiles(host, files, source);
};

export { handleAttachmentUploadFiles, handleAttachmentUploadFromEvent };

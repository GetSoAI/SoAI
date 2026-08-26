/* SoAI - Chat attach modal drop acceptance controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDropAcceptanceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachAvailabilityHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';

const acceptsUploadDrop = (host: ChatAttachAvailabilityHost, _event: DragEvent): boolean => {
    return host.attachments.fileUploadEnabled();
};

const acceptsKnowledgeDrop = <THost>(_host: THost, _event: DragEvent): boolean => {
    return true;
};

export { acceptsKnowledgeDrop, acceptsUploadDrop };

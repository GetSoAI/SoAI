/* SoAI - Physical chat attachment provider status text [frontend/assets/ts/features/chat/attachments/physicalAttachmentProviderStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';

const appendPhysicalAttachmentProviderStatus = (attachment: ChatAttachment, baseStatus: string): string => {
    const suffixes: string[] = [];
    if (attachment.providerMode === 'reference') {
        suffixes.push(i18n.t('chat.attachments.status.referenceOnly'));
    }
    if (attachment.providerTextTruncated === true) {
        suffixes.push(i18n.t('chat.attachments.status.largeTruncated'));
    }
    if (suffixes.length === 0) {
        return baseStatus;
    }
    return [baseStatus, ...suffixes].join(i18n.t('chat.attachments.status.separator'));
};

export { appendPhysicalAttachmentProviderStatus };

/* SoAI - Attachment acquisition lifetime contract [frontend/assets/ts/core/attachments/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface AttachmentAcquisitionScope {
    readonly signal: AbortSignal | null;
    isCurrent(): boolean;
}

export type { AttachmentAcquisitionScope };

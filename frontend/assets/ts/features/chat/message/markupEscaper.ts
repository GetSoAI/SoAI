/* SoAI - Chat feature markup escaper [frontend/assets/ts/features/chat/message/markupEscaper.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type MarkupEscaper = {
    escapeHtml(value: string): string;
    escapeAttribute(value: string): string;
};

export type { MarkupEscaper };

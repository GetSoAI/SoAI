/* SoAI - Conversation export PDF document design tokens [frontend/assets/ts/features/chat/conversationexport/pdfDocumentTokens.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const PDF_PAGE_RULE = '@page { size: A4; margin: 18mm 14mm 16mm; }';
const PDF_FONT_STACK_SANS = '"SoAIType", system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif';
const PDF_COLOR_ACCENT = '#5d7a1e';
const PDF_COLOR_HEADING = '#17202b';
const PDF_COLOR_ASSISTANT_SURFACE = '#f2f2f2';
const PDF_COLOR_EXACT_RULES = 'print-color-adjust: exact; -webkit-print-color-adjust: exact;';

export { PDF_COLOR_ACCENT, PDF_COLOR_ASSISTANT_SURFACE, PDF_COLOR_EXACT_RULES, PDF_COLOR_HEADING, PDF_FONT_STACK_SANS, PDF_PAGE_RULE };

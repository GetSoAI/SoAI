/* SoAI - Chat feature cover styles [frontend/assets/ts/features/chat/conversationexport/coverStyles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { COVER_BRAND_HEIGHT_PX, COVER_HEAD_GAP_PX, COVER_HEAD_MIN_HEIGHT_PX, COVER_KICKER_HEIGHT_PX, COVER_MASTHEAD_BLEED_PX, COVER_MASTHEAD_PADDING_BOTTOM_PX, COVER_MASTHEAD_PADDING_TOP_PX, COVER_NOTE_BORDER_PX, COVER_NOTE_LINE_HEIGHT_PX, COVER_NOTE_PADDING_TOP_PX, COVER_ORIGIN_HEIGHT_PX, COVER_OUTLINE_ROW_GAP_PX, COVER_OUTLINE_ROW_HEIGHT_PX, COVER_PADDING_BLOCK_PX, COVER_PADDING_INLINE_PX, COVER_SECTION_GAP_PX, COVER_SECTION_TITLE_LINE_HEIGHT_PX, COVER_SECTION_TITLE_MARGIN_BOTTOM_PX, COVER_STAT_COLUMNS, COVER_STAT_ROW_GAP_PX, COVER_STAT_ROW_HEIGHT_PX, COVER_TITLE_HEIGHT_PX, COVER_TITLE_LINE_CLAMP, COVER_TITLE_LINE_HEIGHT_PX } from '@features/chat/conversationexport/coverContract.ts';
import { PDF_COLOR_ACCENT, PDF_COLOR_ASSISTANT_SURFACE, PDF_COLOR_EXACT_RULES, PDF_COLOR_HEADING, PDF_FONT_STACK_SANS, PDF_PAGE_RULE } from '@features/chat/conversationexport/pdfDocumentTokens.ts';

const CONVERSATION_EXPORT_COVER_STYLE = `
${PDF_PAGE_RULE}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; font-family: ${PDF_FONT_STACK_SANS}; color: ${PDF_COLOR_HEADING}; ${PDF_COLOR_EXACT_RULES} }
.cover { height: calc(100% - 1px); overflow: hidden; padding: ${COVER_PADDING_BLOCK_PX}px ${COVER_PADDING_INLINE_PX}px; display: flex; flex-direction: column; gap: ${COVER_SECTION_GAP_PX}px; border: 1px solid #b8d2bd; border-radius: 10px; background: linear-gradient(135deg, #ffffff 0%, #eff8ec 52%, #d7efdc 100%); }
.cover-masthead { margin: -${COVER_MASTHEAD_BLEED_PX}px -${COVER_PADDING_INLINE_PX}px 0; padding: ${COVER_MASTHEAD_PADDING_TOP_PX}px ${COVER_PADDING_INLINE_PX}px ${COVER_MASTHEAD_PADDING_BOTTOM_PX}px; display: flex; align-items: stretch; gap: 18px; background: linear-gradient(135deg, #243528 0%, #334b3a 52%, #1e2d22 100%); color: #f1f5ee; }
.cover-brand { display: flex; flex: 0 0 auto; align-items: center; padding-right: 18px; border-right: 1px solid rgba(255, 255, 255, 0.25); }
.cover-brand img { display: block; width: auto; height: ${COVER_BRAND_HEIGHT_PX}px; margin-left: -8px; }
.cover-head { display: flex; flex: 1 1 auto; min-width: 0; min-height: ${COVER_HEAD_MIN_HEIGHT_PX}px; flex-direction: column; justify-content: center; gap: ${COVER_HEAD_GAP_PX}px; }
.cover-kicker { margin: 0; color: #b7d977; font-size: 10px; line-height: ${COVER_KICKER_HEIGHT_PX}px; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cover-title { margin: 0; font-size: 18px; line-height: ${COVER_TITLE_LINE_HEIGHT_PX}px; max-height: ${COVER_TITLE_HEIGHT_PX}px; font-weight: 800; letter-spacing: -0.01em; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: ${COVER_TITLE_LINE_CLAMP}; -webkit-box-orient: vertical; overflow: hidden; }
.cover-origin { margin: 0; color: #a9bfad; font-size: 11px; line-height: ${COVER_ORIGIN_HEIGHT_PX}px; font-weight: 650; letter-spacing: 0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cover-stats { display: grid; grid-template-columns: repeat(${COVER_STAT_COLUMNS}, minmax(0, 1fr)); grid-auto-rows: ${COVER_STAT_ROW_HEIGHT_PX}px; gap: ${COVER_STAT_ROW_GAP_PX}px; }
.stat { display: flex; flex-direction: column; gap: 4px; padding: 7px 12px; border: 1px solid #c8dfc8; border-radius: 8px; background: rgba(255, 255, 255, 0.9); overflow: hidden; }
.stat-label { color: ${PDF_COLOR_ACCENT}; font-size: 10px; line-height: 14px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-value { color: #1c2733; font-size: 9px; line-height: 14px; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cover-section-title { margin: 0 0 ${COVER_SECTION_TITLE_MARGIN_BOTTOM_PX}px; color: #4f721f; font-size: 11px; line-height: ${COVER_SECTION_TITLE_LINE_HEIGHT_PX}px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
.outline-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: ${COVER_OUTLINE_ROW_GAP_PX}px; }
.outline-row { display: flex; height: ${COVER_OUTLINE_ROW_HEIGHT_PX}px; align-items: center; gap: 10px; padding: 0 12px; border: 1px solid #d4e6d1; border-radius: 8px; background: rgba(255, 255, 255, 0.72); }
.outline-index { flex: 0 0 auto; color: #94a3b4; font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums; }
.outline-role { flex: 0 0 auto; min-width: 58px; max-width: 110px; text-align: center; padding: 2px 8px; border-radius: 999px; font-size: 9px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.outline-role--user { background: #e8f3df; color: ${PDF_COLOR_ACCENT}; }
.outline-role--assistant { background: ${PDF_COLOR_ASSISTANT_SURFACE}; color: #5f5f5f; }
.outline-role--tool { background: #fbf2e7; color: #a5621f; }
.outline-role--other { background: #edf5eb; color: #58704d; }
.outline-text { flex: 1 1 auto; min-width: 0; color: #2a3744; font-size: 12px; line-height: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cover-note { margin-top: auto; padding-top: ${COVER_NOTE_PADDING_TOP_PX}px; border-top: ${COVER_NOTE_BORDER_PX}px solid #c2dcc6; color: #6c806b; font-size: 10px; line-height: ${COVER_NOTE_LINE_HEIGHT_PX}px; letter-spacing: 0.04em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
`;

export { CONVERSATION_EXPORT_COVER_STYLE };

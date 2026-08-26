/* SoAI - Conversation export cover layout contract [frontend/assets/ts/features/chat/conversationexport/coverContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const COVER_CONTENT_HEIGHT_PX = 944;
const COVER_SECTION_GAP_PX = 16;
const COVER_SECTION_COUNT = 4;
const COVER_PADDING_BLOCK_PX = 24;
const COVER_PADDING_INLINE_PX = 28;
const COVER_MASTHEAD_PADDING_TOP_PX = 22;
const COVER_MASTHEAD_PADDING_BOTTOM_PX = 18;
const COVER_MASTHEAD_BLEED_PX = COVER_PADDING_BLOCK_PX;
const COVER_BRAND_HEIGHT_PX = 60;
const COVER_HEAD_GAP_PX = 5;
const COVER_HEAD_MIN_HEIGHT_PX = 70;
const COVER_KICKER_HEIGHT_PX = 14;
const COVER_TITLE_LINE_HEIGHT_PX = 22;
const COVER_TITLE_LINE_CLAMP = 2;
const COVER_TITLE_HEIGHT_PX = COVER_TITLE_LINE_HEIGHT_PX * COVER_TITLE_LINE_CLAMP;
const COVER_ORIGIN_HEIGHT_PX = 18;
const COVER_STAT_COLUMNS = 2;
const COVER_STAT_ROW_HEIGHT_PX = 48;
const COVER_STAT_ROW_GAP_PX = 9;
const COVER_SECTION_TITLE_LINE_HEIGHT_PX = 14;
const COVER_SECTION_TITLE_MARGIN_BOTTOM_PX = 10;
const COVER_OUTLINE_HEADER_HEIGHT_PX = COVER_SECTION_TITLE_LINE_HEIGHT_PX + COVER_SECTION_TITLE_MARGIN_BOTTOM_PX;
const COVER_OUTLINE_ROW_HEIGHT_PX = 30;
const COVER_OUTLINE_ROW_GAP_PX = 5;
const COVER_NOTE_LINE_HEIGHT_PX = 14;
const COVER_NOTE_PADDING_TOP_PX = 13;
const COVER_NOTE_BORDER_PX = 1;
const COVER_NOTE_HEIGHT_PX = COVER_NOTE_LINE_HEIGHT_PX + COVER_NOTE_PADDING_TOP_PX + COVER_NOTE_BORDER_PX;

const COVER_OUTLINE_ROLE_MAX_LENGTH = 40;
const COVER_OUTLINE_PREVIEW_MAX_LENGTH = 240;
const COVER_ORIGIN_MAX_LENGTH = 120;

const resolveCoverStatsHeight = (summaryItemCount: number): number => {
    const statRows = Math.ceil(summaryItemCount / COVER_STAT_COLUMNS);
    if (statRows <= 0) {
        return 0;
    }
    return statRows * COVER_STAT_ROW_HEIGHT_PX + (statRows - 1) * COVER_STAT_ROW_GAP_PX;
};

const resolveCoverOutlineHeight = (outlineRowCount: number): number => {
    if (outlineRowCount <= 0) {
        return 0;
    }
    return outlineRowCount * COVER_OUTLINE_ROW_HEIGHT_PX + (outlineRowCount - 1) * COVER_OUTLINE_ROW_GAP_PX;
};

const resolveCoverMastheadHeight = (hasOriginLine: boolean): number => {
    const originHeight = hasOriginLine ? COVER_HEAD_GAP_PX + COVER_ORIGIN_HEIGHT_PX : 0;
    const headHeight = Math.max(COVER_HEAD_MIN_HEIGHT_PX, COVER_KICKER_HEIGHT_PX + COVER_HEAD_GAP_PX + COVER_TITLE_HEIGHT_PX + originHeight);
    return COVER_MASTHEAD_PADDING_TOP_PX + Math.max(COVER_BRAND_HEIGHT_PX, headHeight) + COVER_MASTHEAD_PADDING_BOTTOM_PX - COVER_MASTHEAD_BLEED_PX;
};

const resolveCoverFixedHeight = (hasOriginLine: boolean): number => {
    return resolveCoverMastheadHeight(hasOriginLine) + COVER_OUTLINE_HEADER_HEIGHT_PX + COVER_NOTE_HEIGHT_PX + (COVER_SECTION_COUNT - 1) * COVER_SECTION_GAP_PX;
};

const resolveConversationExportOutlineCapacity = (options: { summaryItemCount: number; hasOriginLine: boolean }): number => {
    const availableHeight = COVER_CONTENT_HEIGHT_PX - resolveCoverFixedHeight(options.hasOriginLine) - resolveCoverStatsHeight(options.summaryItemCount);
    const rowStride = COVER_OUTLINE_ROW_HEIGHT_PX + COVER_OUTLINE_ROW_GAP_PX;
    return Math.max(0, Math.floor((availableHeight + COVER_OUTLINE_ROW_GAP_PX) / rowStride));
};

const clampCoverFieldText = (value: string, maxLength: number): string => {
    const normalized = toTrimmedString(value);
    const codePoints = Array.from(normalized);
    if (codePoints.length <= maxLength) {
        return normalized;
    }
    return toTrimmedString(codePoints.slice(0, maxLength).join(''));
};

export { clampCoverFieldText, COVER_BRAND_HEIGHT_PX, COVER_CONTENT_HEIGHT_PX, COVER_HEAD_GAP_PX, COVER_HEAD_MIN_HEIGHT_PX, COVER_KICKER_HEIGHT_PX, COVER_MASTHEAD_BLEED_PX, COVER_MASTHEAD_PADDING_BOTTOM_PX, COVER_MASTHEAD_PADDING_TOP_PX, COVER_NOTE_BORDER_PX, COVER_NOTE_LINE_HEIGHT_PX, COVER_NOTE_PADDING_TOP_PX, COVER_ORIGIN_HEIGHT_PX, COVER_ORIGIN_MAX_LENGTH, COVER_OUTLINE_PREVIEW_MAX_LENGTH, COVER_OUTLINE_ROLE_MAX_LENGTH, COVER_OUTLINE_ROW_GAP_PX, COVER_OUTLINE_ROW_HEIGHT_PX, COVER_PADDING_BLOCK_PX, COVER_PADDING_INLINE_PX, COVER_SECTION_GAP_PX, COVER_SECTION_TITLE_LINE_HEIGHT_PX, COVER_SECTION_TITLE_MARGIN_BOTTOM_PX, COVER_STAT_COLUMNS, COVER_STAT_ROW_GAP_PX, COVER_STAT_ROW_HEIGHT_PX, COVER_TITLE_HEIGHT_PX, COVER_TITLE_LINE_CLAMP, COVER_TITLE_LINE_HEIGHT_PX, resolveConversationExportOutlineCapacity, resolveCoverFixedHeight, resolveCoverOutlineHeight, resolveCoverStatsHeight };

/* SoAI - Chat feature inline tool header preview resolvers [frontend/assets/ts/features/chat/message/messageview/inlineToolHeaderPreviewResolvers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { clampToolHeaderPreview } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { resolveFirstCompactStringField, resolveFirstIntegerField, resolvePayloadRecord, tryExtractRecord, tryExtractWaitArguments, tryResolveCompactStringField } from '@features/chat/toolactivity/payloadReaders.ts';
import { resolveApplyPatchHeaderPreview } from '@features/chat/message/messageview/applyPatchHeaderPreview.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';

const WEATHER_LOCATION_KEYS = ['location', 'city', 'place'];
const WEATHER_FORECAST_DAYS_KEYS = ['forecast_days', 'days'];
const DATETIME_RESULT_KEYS = ['datetime_formatted', 'datetime_iso'];

type InlineToolHeaderPreviewResolver = (segment: InlineToolActivitySegment, toolLeafName: string) => string | null;

const resolveWeatherToolHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'weather' || segment.inputArguments === undefined || segment.inputArguments === null) {
        return null;
    }
    const argumentsRecord = resolvePayloadRecord(segment.inputArguments);
    if (!argumentsRecord) {
        return null;
    }
    const location = resolveFirstCompactStringField(argumentsRecord, WEATHER_LOCATION_KEYS);
    const forecastDays = resolveFirstIntegerField(argumentsRecord, WEATHER_FORECAST_DAYS_KEYS);
    const parts: string[] = [];
    if (location) {
        parts.push(location);
    }
    if (forecastDays !== null) {
        parts.push(i18n.t('common.time.units.day.short', { count: String(forecastDays) }));
    }
    return parts.length > 0 ? clampToolHeaderPreview(parts.join(' - ')) : null;
};

const resolveWaitHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'wait') {
        return null;
    }
    if (segment.inputArguments === undefined || segment.inputArguments === null) {
        return '';
    }
    const waitArguments = tryExtractWaitArguments(segment.inputArguments);
    const previewParts: string[] = [];
    if (waitArguments.seconds !== null) {
        previewParts.push(formatCompactDurationFromMs(waitArguments.seconds * 1000));
    }
    if (waitArguments.reason) {
        previewParts.push(waitArguments.reason);
    }
    return previewParts.join(', ');
};

const resolveDatetimeCurrentHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'datetime_current') {
        return null;
    }
    const resultRecord = segment.result !== undefined && segment.result !== null ? tryExtractRecord(segment.result) : null;
    if (resultRecord) {
        const resultDatetime = resolveFirstCompactStringField(resultRecord, DATETIME_RESULT_KEYS);
        if (resultDatetime) {
            return clampToolHeaderPreview(resultDatetime);
        }
    }
    const argumentsRecord = segment.inputArguments !== undefined && segment.inputArguments !== null ? resolvePayloadRecord(segment.inputArguments) : null;
    if (argumentsRecord) {
        const argumentDatetime = tryResolveCompactStringField(argumentsRecord, 'datetime_str');
        if (argumentDatetime) {
            return clampToolHeaderPreview(argumentDatetime);
        }
    }
    return '';
};

const resolveListDirHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'list_dir') {
        return null;
    }
    const resultRecord = segment.result !== undefined && segment.result !== null ? tryExtractRecord(segment.result) : null;
    if (resultRecord) {
        const resultPath = tryResolveCompactStringField(resultRecord, 'path');
        if (resultPath) {
            return clampToolHeaderPreview(resultPath);
        }
    }
    const argumentsRecord = segment.inputArguments !== undefined && segment.inputArguments !== null ? resolvePayloadRecord(segment.inputArguments) : null;
    if (argumentsRecord) {
        const argumentPath = tryResolveCompactStringField(argumentsRecord, 'path');
        if (argumentPath) {
            return clampToolHeaderPreview(argumentPath);
        }
    }
    return '';
};

const resolveUnitConvertHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'unit_convert') {
        return null;
    }
    const argumentsRecord = segment.inputArguments !== undefined && segment.inputArguments !== null ? resolvePayloadRecord(segment.inputArguments) : null;
    if (!argumentsRecord) {
        return '';
    }
    const rawValue = argumentsRecord['value'];
    const valueText = typeof rawValue === 'number' && Number.isFinite(rawValue) ? String(rawValue) : null;
    const fromUnit = tryResolveCompactStringField(argumentsRecord, 'from_unit');
    const toUnit = tryResolveCompactStringField(argumentsRecord, 'to_unit');
    const sourceParts: string[] = [];
    if (valueText) {
        sourceParts.push(valueText);
    }
    if (fromUnit) {
        sourceParts.push(fromUnit);
    }
    const sourceText = sourceParts.join(' ');
    if (sourceText && toUnit) {
        return clampToolHeaderPreview(`${sourceText} → ${toUnit}`);
    }
    if (sourceText) {
        return clampToolHeaderPreview(sourceText);
    }
    if (toUnit) {
        return clampToolHeaderPreview(toUnit);
    }
    return '';
};

const resolveWriteStdinHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'shell_write_stdin') {
        return null;
    }
    const argumentsRecord = segment.inputArguments !== undefined && segment.inputArguments !== null ? resolvePayloadRecord(segment.inputArguments) : null;
    if (argumentsRecord) {
        const stdinChars = tryResolveCompactStringField(argumentsRecord, 'chars');
        if (stdinChars) {
            return clampToolHeaderPreview(stdinChars);
        }
    }
    return '';
};

const TOOL_HEADER_PREVIEW_RESOLVERS: readonly InlineToolHeaderPreviewResolver[] = [resolveWaitHeaderPreview, resolveWeatherToolHeaderPreview, resolveApplyPatchHeaderPreview, resolveDatetimeCurrentHeaderPreview, resolveListDirHeaderPreview, resolveUnitConvertHeaderPreview, resolveWriteStdinHeaderPreview];

const resolveToolSpecificHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    for (const resolver of TOOL_HEADER_PREVIEW_RESOLVERS) {
        const preview = resolver(segment, toolLeafName);
        if (preview !== null) {
            return preview;
        }
    }
    return null;
};

export { resolveToolSpecificHeaderPreview };

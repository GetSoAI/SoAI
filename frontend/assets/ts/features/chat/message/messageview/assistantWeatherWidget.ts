/* SoAI - Chat feature assistant weather widget [frontend/assets/ts/features/chat/message/messageview/assistantWeatherWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatMessageRenderHost, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { resolveToolResultWeatherPayload, type ToolResultWeatherPayload, type WeatherDailyPayload, type WeatherHourlyPayload } from '@features/chat/message/messageview/toolResultWeatherPayload.ts';
import { renderAssistantActivityWidgetFooter } from '@features/chat/message/messageview/assistantActivityWidgetFooter.ts';
import { WEATHER_FORECAST_ICON_OPTIONS, WEATHER_HEADER_ICON_OPTIONS, resolveWeatherIconName } from '@features/chat/message/messageview/weatherWidgetIcons.ts';
import { renderDayPanel } from '@features/chat/message/messageview/weatherWidgetDayDetail.ts';
import { MIN_VISIBLE_PRECIP_PERCENT, formatDailyRange, formatDayLabel, formatDayNumber, formatHourLabel, formatHourlyRange, formatWeatherForecastDayCount, formatWeatherMeasurementUnitsLabel, formatWeatherTemperature, normalizeConditionAttribute, resolveLocalIsoDate, type UnitSystem } from '@features/chat/message/messageview/weatherWidgetFormatters.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const WEATHER_TOOL_NAME = 'weather';

const renderWeatherScope = (host: ChatMessageRenderHost, payload: ToolResultWeatherPayload, locationLabel: string): string => {
    const location = locationLabel.trim() || i18n.t('common.notAvailableShort');
    const days = formatWeatherForecastDayCount(payload.daily.length);
    const unitSystem = formatWeatherMeasurementUnitsLabel();
    return [location, days, unitSystem].map((value) => host.escapeHtml(value)).join(' &middot; ');
};

const renderWeatherHeader = (host: ChatMessageRenderHost, payload: ToolResultWeatherPayload, locationLabel: string): string => {
    const headerIcon = host.getIconHtml('weather-cloud', WEATHER_HEADER_ICON_OPTIONS);
    const label = host.escapeHtml(i18n.t('chat.weather.label'));
    const dailyRangeText = formatDailyRange(payload.daily);
    const dailyRange = dailyRangeText ? `<span class="assistant-weather-widget__query">${host.escapeHtml(dailyRangeText)}</span>` : '';
    const scope = renderWeatherScope(host, payload, locationLabel);
    return ['<header class="assistant-weather-widget__header">', '<span class="assistant-weather-widget__title">', `<span class="assistant-weather-widget__title-icon">${headerIcon}</span>`, `<span class="assistant-weather-widget__label">${label}</span>`, dailyRange, '</span>', `<span class="assistant-weather-widget__scope">${scope}</span>`, '</header>'].join('');
};

const renderHourlyEntry = (host: ChatMessageRenderHost, entry: WeatherHourlyPayload, unitSystem: UnitSystem, isNow: boolean): string => {
    const icon = host.getIconHtml(resolveWeatherIconName(entry.conditionType, entry.isDay), WEATHER_FORECAST_ICON_OPTIONS);
    const label = host.escapeHtml(formatHourLabel(entry.time));
    const temperature = host.escapeHtml(formatWeatherTemperature(entry.temperature, unitSystem));
    const condition = host.escapeAttribute(normalizeConditionAttribute(entry.conditionType));
    const precipChance = Math.round(entry.precipitationProbability);
    const precipLabel = host.escapeHtml(i18n.t('chat.weather.precipitation'));
    const precip = precipChance >= MIN_VISIBLE_PRECIP_PERCENT ? `<span class="assistant-weather-widget__hour-precip" aria-label="${precipLabel}">${String(precipChance)}%</span>` : '<span class="assistant-weather-widget__hour-precip" aria-hidden="true"></span>';
    const nowAttribute = isNow ? ' aria-current="time"' : '';
    return [`<div class="assistant-weather-widget__hour"${nowAttribute}>`, `<span class="assistant-weather-widget__hour-label">${label}</span>`, `<span class="assistant-weather-widget__hour-icon" data-condition="${condition}">${icon}</span>`, precip, `<span class="assistant-weather-widget__hour-temp">${temperature}</span>`, '</div>'].join('');
};

const renderHourlyStrip = (host: ChatMessageRenderHost, payload: ToolResultWeatherPayload): string => {
    if (payload.hourly.length === 0) {
        return '';
    }
    const titleText = i18n.t('chat.weather.hourly');
    const title = host.escapeHtml(titleText);
    const ariaLabel = host.escapeAttribute(titleText);
    const rangeText = formatHourlyRange(payload.hourly);
    const range = rangeText ? `<span class="assistant-weather-widget__strip-range">${host.escapeHtml(rangeText)}</span>` : '';
    const entries = payload.hourly.map((entry, index) => renderHourlyEntry(host, entry, payload.unitSystem, index === 0)).join('');
    return [`<div class="assistant-weather-widget__strip" aria-label="${ariaLabel}">`, '<header class="assistant-weather-widget__strip-header">', `<span class="assistant-weather-widget__strip-title">${title}</span>`, range, '</header>', `<div class="assistant-weather-widget__hourly">${entries}</div>`, '</div>'].join('');
};

const renderForecastCard = (host: ChatMessageRenderHost, entry: WeatherDailyPayload, unitSystem: UnitSystem, isToday: boolean, radioId: string): string => {
    const icon = host.getIconHtml(resolveWeatherIconName(entry.conditionType), WEATHER_FORECAST_ICON_OPTIONS);
    const label = host.escapeHtml(formatDayLabel(entry.date));
    const dayNumber = host.escapeHtml(formatDayNumber(entry.date));
    const max = host.escapeHtml(formatWeatherTemperature(entry.temperatureMax, unitSystem));
    const min = host.escapeHtml(formatWeatherTemperature(entry.temperatureMin, unitSystem));
    const condition = host.escapeAttribute(normalizeConditionAttribute(entry.conditionType));
    const precipChance = Math.round(entry.precipitationProbability);
    const precipLabel = host.escapeHtml(i18n.t('chat.weather.precipitation'));
    const precip = precipChance >= MIN_VISIBLE_PRECIP_PERCENT ? `<span class="assistant-weather-widget__day-precip" aria-label="${precipLabel}">${String(precipChance)}%</span>` : '<span class="assistant-weather-widget__day-precip" aria-hidden="true"></span>';
    const todayAttribute = isToday ? ' aria-current="date"' : '';
    return [`<label class="assistant-weather-widget__day" for="${host.escapeAttribute(radioId)}"${todayAttribute}>`, `<span class="assistant-weather-widget__day-label">${label}</span>`, `<span class="assistant-weather-widget__day-date">${dayNumber}</span>`, `<span class="assistant-weather-widget__day-icon" data-condition="${condition}">${icon}</span>`, precip, `<span class="assistant-weather-widget__day-temp"><strong>${max}</strong><span>${min}</span></span>`, '</label>'].join('');
};

const renderWeatherWidget = (host: ChatMessageRenderHost, payload: ToolResultWeatherPayload, callId: string, startedAtMs: number | undefined): string => {
    const locationParts = [payload.locationName, payload.admin1, payload.country].filter((value) => Boolean(value));
    const locationLabel = locationParts.join(', ');
    const location = host.escapeHtml(locationLabel);
    const todayIsoDate = resolveLocalIsoDate();
    const radioGroupName = `weather-day-${callId}`;
    const hourlyHtml = renderHourlyStrip(host, payload);
    const todayIndex = payload.daily.findIndex((entry) => entry.date === todayIsoDate);
    const selectedIndex = todayIndex >= 0 ? todayIndex : 0;
    const panels = payload.daily
        .map((entry, index) => {
            const radioId = `weather-day-${callId}-${String(index)}`;
            return renderDayPanel(host, payload, entry, index === selectedIndex, entry.date === todayIsoDate, location, radioId, radioGroupName, hourlyHtml);
        })
        .join('');
    const cards = payload.daily.map((entry, index) => renderForecastCard(host, entry, payload.unitSystem, entry.date === todayIsoDate, `weather-day-${callId}-${String(index)}`)).join('');
    const forecastTitle = host.escapeHtml(i18n.t('chat.weather.forecast'));
    const forecastRangeText = formatDailyRange(payload.daily);
    const forecastRange = forecastRangeText ? `<span class="assistant-weather-widget__strip-range">${host.escapeHtml(forecastRangeText)}</span>` : '';
    const headlineCondition = host.escapeAttribute(normalizeConditionAttribute(payload.current.conditionType));
    const headlineTimeOfDay = payload.current.isDay ? 'day' : 'night';
    const ariaLabel = host.escapeAttribute(i18n.t('chat.weather.label'));
    return [`<section class="assistant-weather-widget" aria-label="${ariaLabel}" data-condition="${headlineCondition}" data-time-of-day="${headlineTimeOfDay}">`, renderWeatherHeader(host, payload, locationLabel), panels, '<div class="assistant-weather-widget__strip">', '<header class="assistant-weather-widget__strip-header">', `<span class="assistant-weather-widget__strip-title">${forecastTitle}</span>`, forecastRange, '</header>', `<div class="assistant-weather-widget__forecast">${cards}</div>`, '</div>', renderAssistantActivityWidgetFooter(host, startedAtMs), '</section>'].join('');
};

const renderAssistantWeatherWidget = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    if (segment.type !== 'inline_tool_activity') {
        return '';
    }
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    if (segment.status !== 'completed' || toolLeafName !== WEATHER_TOOL_NAME) {
        return '';
    }
    const payload = resolveToolResultWeatherPayload(segment.result);
    if (payload === null) {
        return '';
    }
    return renderWeatherWidget(host, payload, segment.callId, segment.startedAtMs);
};

export { renderAssistantWeatherWidget };

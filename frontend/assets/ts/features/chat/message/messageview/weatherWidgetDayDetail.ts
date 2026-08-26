/* SoAI - Chat feature weather widget day detail [frontend/assets/ts/features/chat/message/messageview/weatherWidgetDayDetail.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import type { ToolResultWeatherPayload, WeatherCurrentPayload, WeatherDailyPayload } from '@features/chat/message/messageview/toolResultWeatherPayload.ts';
import { WEATHER_ICON_OPTIONS, resolveWeatherIconName } from '@features/chat/message/messageview/weatherWidgetIcons.ts';
import { formatWeatherTemperature, formatWholePercent, formatWindWithDirection, normalizeConditionAttribute, type UnitSystem } from '@features/chat/message/messageview/weatherWidgetFormatters.ts';

const renderMetric = (host: ChatMessageRenderHost, label: string, value: string): string => `<span class="assistant-weather-widget__metric"><span>${host.escapeHtml(label)}</span><strong>${host.escapeHtml(value)}</strong></span>`;

const renderTodayMetrics = (host: ChatMessageRenderHost, current: WeatherCurrentPayload, unitSystem: UnitSystem): string => [renderMetric(host, i18n.t('chat.weather.feelsLike'), formatWeatherTemperature(current.apparentTemperature, unitSystem)), renderMetric(host, i18n.t('chat.weather.humidity'), formatWholePercent(current.relativeHumidity)), renderMetric(host, i18n.t('chat.weather.wind'), formatWindWithDirection(current.windSpeed, current.windDirection, unitSystem)), renderMetric(host, i18n.t('chat.weather.clouds'), formatWholePercent(current.cloudCover))].join('');

const renderForecastMetrics = (host: ChatMessageRenderHost, entry: WeatherDailyPayload, unitSystem: UnitSystem): string => [renderMetric(host, i18n.t('chat.weather.feelsLike'), formatWeatherTemperature(entry.apparentTemperatureMax, unitSystem)), renderMetric(host, i18n.t('chat.weather.humidity'), formatWholePercent(entry.relativeHumidityMean)), renderMetric(host, i18n.t('chat.weather.wind'), formatWindWithDirection(entry.windSpeedMax, entry.windDirectionDominant, unitSystem)), renderMetric(host, i18n.t('chat.weather.clouds'), formatWholePercent(entry.cloudCoverMean))].join('');

const renderCurrentBlock = (host: ChatMessageRenderHost, locationHtml: string, conditionType: string, isDay: boolean, temperatureValue: number, conditionText: string, unitSystem: UnitSystem, highLowText: string): string => {
    const iconHtml = host.getIconHtml(resolveWeatherIconName(conditionType, isDay), WEATHER_ICON_OPTIONS);
    const conditionAttribute = host.escapeAttribute(normalizeConditionAttribute(conditionType));
    const timeOfDay = isDay ? 'day' : 'night';
    const temperatureHtml = host.escapeHtml(formatWeatherTemperature(temperatureValue, unitSystem));
    const conditionHtml = host.escapeHtml(conditionText);
    const highLow = highLowText ? ` &middot; ${host.escapeHtml(highLowText)}` : '';
    return ['<div class="assistant-weather-widget__current">', `<div class="assistant-weather-widget__icon" data-condition="${conditionAttribute}" data-time-of-day="${timeOfDay}">${iconHtml}</div>`, '<div class="assistant-weather-widget__summary">', `<span class="assistant-weather-widget__location">${locationHtml}</span>`, `<span class="assistant-weather-widget__temperature">${temperatureHtml}</span>`, `<span class="assistant-weather-widget__condition">${conditionHtml}${highLow}</span>`, '</div></div>'].join('');
};

const renderDayPanel = (host: ChatMessageRenderHost, payload: ToolResultWeatherPayload, entry: WeatherDailyPayload, isSelected: boolean, isToday: boolean, locationHtml: string, radioId: string, radioGroupName: string, hourlyHtml: string): string => {
    const checked = isSelected ? ' checked' : '';
    const dayConditionType = isToday ? payload.current.conditionType : entry.conditionType;
    const dayIsDay = isToday ? payload.current.isDay : true;
    const dayConditionAttr = host.escapeAttribute(normalizeConditionAttribute(dayConditionType));
    const dayTimeOfDayAttr = dayIsDay ? 'day' : 'night';
    const radio = `<input class="assistant-weather-widget__day-selector visually-hidden" type="radio" id="${host.escapeAttribute(radioId)}" name="${host.escapeAttribute(radioGroupName)}" data-condition="${dayConditionAttr}" data-time-of-day="${dayTimeOfDayAttr}"${checked}>`;
    const highLow = `${formatWeatherTemperature(entry.temperatureMax, payload.unitSystem)} / ${formatWeatherTemperature(entry.temperatureMin, payload.unitSystem)}`;
    const current = isToday ? renderCurrentBlock(host, locationHtml, payload.current.conditionType, payload.current.isDay, payload.current.temperature, payload.current.conditionText, payload.unitSystem, highLow) : renderCurrentBlock(host, locationHtml, entry.conditionType, true, entry.temperatureMax, entry.conditionText, payload.unitSystem, highLow);
    const metrics = isToday ? renderTodayMetrics(host, payload.current, payload.unitSystem) : renderForecastMetrics(host, entry, payload.unitSystem);
    const hourly = isToday ? hourlyHtml : '';
    return [radio, '<div class="assistant-weather-widget__detail-panel">', current, hourly, `<div class="assistant-weather-widget__metrics">${metrics}</div>`, '</div>'].join('');
};

export { renderDayPanel };

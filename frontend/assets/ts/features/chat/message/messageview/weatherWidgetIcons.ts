/* SoAI - Chat feature weather widget icons [frontend/assets/ts/features/chat/message/messageview/weatherWidgetIcons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const WEATHER_ICON_OPTIONS = { size: 48, strokeWidth: 1.8 };
const WEATHER_HEADER_ICON_OPTIONS = { size: 16, strokeWidth: 1.5 };
const WEATHER_FORECAST_ICON_OPTIONS = { size: 22, strokeWidth: 1.7 };

const resolveWeatherIconName = (conditionType: string, isDay: boolean = true): IconName => {
    const normalized = conditionType.trim().toLowerCase();
    if (normalized === 'clear' || normalized === 'mostly_clear') {
        return isDay ? 'weather-sun' : 'weather-moon';
    }
    if (normalized === 'partly_cloudy' || normalized === 'cloudy') {
        return 'weather-cloud';
    }
    if (normalized === 'fog') {
        return 'weather-fog';
    }
    if (normalized === 'snow') {
        return 'weather-snow';
    }
    if (normalized.includes('thunder')) {
        return 'weather-thunder';
    }
    if (normalized.includes('rain') || normalized.includes('drizzle') || normalized === 'showers') {
        return 'weather-rain';
    }
    return 'weather-cloud';
};

export { WEATHER_FORECAST_ICON_OPTIONS, WEATHER_HEADER_ICON_OPTIONS, WEATHER_ICON_OPTIONS, resolveWeatherIconName };

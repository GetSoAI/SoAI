/* SoAI - Chat feature tool result weather payload [frontend/assets/ts/features/chat/message/messageview/toolResultWeatherPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface WeatherConditionPayload {
    conditionText: string;
    conditionType: string;
    weatherCode: number;
}

interface WeatherCurrentPayload extends WeatherConditionPayload {
    apparentTemperature: number;
    cloudCover: number;
    isDay: boolean;
    relativeHumidity: number;
    temperature: number;
    time: string;
    windDirection: number;
    windSpeed: number;
}

interface WeatherDailyPayload extends WeatherConditionPayload {
    apparentTemperatureMax: number;
    apparentTemperatureMin: number;
    cloudCoverMean: number;
    date: string;
    precipitationProbability: number;
    relativeHumidityMean: number;
    temperatureMax: number;
    temperatureMin: number;
    windDirectionDominant: number;
    windSpeedMax: number;
}

interface WeatherHourlyPayload extends WeatherConditionPayload {
    isDay: boolean;
    precipitation: number;
    precipitationProbability: number;
    temperature: number;
    time: string;
    windSpeed: number;
}

interface ToolResultWeatherPayload {
    admin1: string | null;
    country: string;
    current: WeatherCurrentPayload;
    daily: WeatherDailyPayload[];
    hourly: WeatherHourlyPayload[];
    locationName: string;
    unitSystem: 'metric' | 'imperial';
}

const optionalTrimmedString = (value: JsonValue | undefined): string | null => {
    if (!isString(value) || !value.trim()) {
        return null;
    }
    return value.trim();
};

const readRequiredString = (record: JsonObject, key: string): string | null => {
    const value = optionalTrimmedString(record[key]);
    return value === null ? null : value;
};

const readNumber = (record: JsonObject, key: string): number | null => {
    const value = record[key];
    return isFiniteNumber(value) ? value : null;
};

const readCondition = (record: JsonObject): WeatherConditionPayload | null => {
    const conditionType = readRequiredString(record, 'condition_type');
    const conditionText = readRequiredString(record, 'condition_text');
    const weatherCode = readNumber(record, 'weather_code');
    if (conditionType === null || conditionText === null || weatherCode === null) {
        return null;
    }
    return { conditionText, conditionType, weatherCode };
};

const readCurrent = (value: JsonValue | undefined): WeatherCurrentPayload | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const condition = readCondition(value);
    const time = readRequiredString(value, 'time');
    const temperature = readNumber(value, 'temperature');
    const apparentTemperature = readNumber(value, 'apparent_temperature');
    const relativeHumidity = readNumber(value, 'relative_humidity');
    const cloudCover = readNumber(value, 'cloud_cover');
    const windSpeed = readNumber(value, 'wind_speed');
    const windDirection = readNumber(value, 'wind_direction');
    const isDay = value['is_day'];
    if (condition === null || time === null || temperature === null || apparentTemperature === null || relativeHumidity === null || cloudCover === null || windSpeed === null || windDirection === null || !isBoolean(isDay)) {
        return null;
    }
    return {
        ...condition,
        apparentTemperature,
        cloudCover,
        isDay,
        relativeHumidity,
        temperature,
        time,
        windDirection,
        windSpeed
    };
};

const readDailyEntry = (value: JsonValue | undefined): WeatherDailyPayload | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const condition = readCondition(value);
    const date = readRequiredString(value, 'date');
    const temperatureMax = readNumber(value, 'temperature_max');
    const temperatureMin = readNumber(value, 'temperature_min');
    const apparentTemperatureMax = readNumber(value, 'apparent_temperature_max');
    const apparentTemperatureMin = readNumber(value, 'apparent_temperature_min');
    const precipitationProbability = readNumber(value, 'precipitation_probability');
    const windSpeedMax = readNumber(value, 'wind_speed_max');
    const windDirectionDominant = readNumber(value, 'wind_direction_dominant');
    const relativeHumidityMean = readNumber(value, 'relative_humidity_mean');
    const cloudCoverMean = readNumber(value, 'cloud_cover_mean');
    if (condition === null || date === null || temperatureMax === null || temperatureMin === null || apparentTemperatureMax === null || apparentTemperatureMin === null || precipitationProbability === null || windSpeedMax === null || windDirectionDominant === null || relativeHumidityMean === null || cloudCoverMean === null) {
        return null;
    }
    return {
        ...condition,
        apparentTemperatureMax,
        apparentTemperatureMin,
        cloudCoverMean,
        date,
        precipitationProbability,
        relativeHumidityMean,
        temperatureMax,
        temperatureMin,
        windDirectionDominant,
        windSpeedMax
    };
};

const readDaily = (value: JsonValue | undefined): WeatherDailyPayload[] | null => {
    if (!isJsonArray(value)) {
        return null;
    }
    const entries = value.map(readDailyEntry).filter((entry): entry is WeatherDailyPayload => entry !== null);
    return entries.length > 0 ? entries.slice(0, 14) : null;
};

const readHourlyEntry = (value: JsonValue | undefined): WeatherHourlyPayload | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const condition = readCondition(value);
    const time = readRequiredString(value, 'time');
    const temperature = readNumber(value, 'temperature');
    const precipitationProbability = readNumber(value, 'precipitation_probability');
    const precipitation = readNumber(value, 'precipitation');
    const windSpeed = readNumber(value, 'wind_speed');
    const isDay = value['is_day'];
    if (condition === null || time === null || temperature === null || precipitationProbability === null || precipitation === null || windSpeed === null || !isBoolean(isDay)) {
        return null;
    }
    return {
        ...condition,
        isDay,
        precipitation,
        precipitationProbability,
        temperature,
        time,
        windSpeed
    };
};

const readHourly = (value: JsonValue | undefined): WeatherHourlyPayload[] | null => {
    if (value === undefined) {
        return [];
    }
    if (!isJsonArray(value)) {
        return null;
    }
    const entries = value.map(readHourlyEntry).filter((entry): entry is WeatherHourlyPayload => entry !== null);
    return entries.slice(0, 48);
};

const resolveToolResultWeatherPayload = (payload: JsonValue | undefined): ToolResultWeatherPayload | null => {
    if (!isJsonObject(payload) || payload['provider'] !== 'open_meteo') {
        return null;
    }
    const locationName = readRequiredString(payload, 'location_name');
    const country = readRequiredString(payload, 'country');
    const unitSystemRaw = payload['unit_system'];
    const unitSystem = unitSystemRaw === 'imperial' ? 'imperial' : unitSystemRaw === 'metric' ? 'metric' : null;
    const current = readCurrent(payload['current']);
    const daily = readDaily(payload['daily']);
    const hourly = readHourly(payload['hourly']);
    if (locationName === null || country === null || unitSystem === null || current === null || daily === null || hourly === null) {
        return null;
    }
    return {
        admin1: optionalTrimmedString(payload['admin1']),
        country,
        current,
        daily,
        hourly,
        locationName,
        unitSystem
    };
};

export { resolveToolResultWeatherPayload };
export type { ToolResultWeatherPayload, WeatherCurrentPayload, WeatherDailyPayload, WeatherHourlyPayload };

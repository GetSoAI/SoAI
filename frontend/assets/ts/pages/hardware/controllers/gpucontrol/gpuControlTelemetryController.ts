/* SoAI - Hardware page GPU control telemetry controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatTemperature } from '@core/localization/public.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { resolveTemperatureSeverity, type TemperatureSeverity } from '@features/hardware/public.ts';

interface GpuControlTelemetry {
    temperatureCelsius: number | null;
    coreUtilizationPercent: number | null;
    memoryUtilizationPercent: number | null;
    powerDrawWatts: number | null;
    powerLimitWatts: number | null;
}

const hasTelemetry = (telemetry: GpuControlTelemetry | null): telemetry is GpuControlTelemetry => {
    return !!telemetry && (isFiniteNumber(telemetry.temperatureCelsius) || isFiniteNumber(telemetry.coreUtilizationPercent) || isFiniteNumber(telemetry.memoryUtilizationPercent) || (isFiniteNumber(telemetry.powerDrawWatts) && isFiniteNumber(telemetry.powerLimitWatts) && telemetry.powerLimitWatts > 0));
};

const normalizeTelemetryValue = (value: number | null): number | null => {
    return isFiniteNumber(value) ? value : null;
};

const formatTelemetryTemperature = (value: number): string => {
    return formatTemperature(value, 0);
};

const resolveGpuControlTelemetryTemperatureSeverity = (telemetry: GpuControlTelemetry | null): TemperatureSeverity => {
    return resolveTemperatureSeverity(telemetry?.temperatureCelsius);
};

const formatTelemetryPercent = (label: string, value: number): string => {
    return `${label} ${formatPercent(value, 0)}`;
};

const formatTelemetryPower = (telemetry: GpuControlTelemetry): string | null => {
    if (!isFiniteNumber(telemetry.powerDrawWatts) || !isFiniteNumber(telemetry.powerLimitWatts) || telemetry.powerLimitWatts <= 0) {
        return null;
    }
    return `${i18n.t('hardware.gpu.telemetry.powerDraw')} ${formatPercent((telemetry.powerDrawWatts / telemetry.powerLimitWatts) * 100, 0)}`;
};

const formatGpuControlTelemetryLabel = (telemetry: GpuControlTelemetry | null): string => {
    if (!hasTelemetry(telemetry)) {
        return '';
    }
    const parts: string[] = [];
    if (isFiniteNumber(telemetry.temperatureCelsius)) {
        parts.push(`${i18n.t('hardware.gpu.telemetry.temperatures')} ${formatTelemetryTemperature(telemetry.temperatureCelsius)}`);
    }
    if (isFiniteNumber(telemetry.coreUtilizationPercent)) {
        parts.push(formatTelemetryPercent(i18n.t('hardware.gpu.telemetry.coreUtilization'), telemetry.coreUtilizationPercent));
    }
    if (isFiniteNumber(telemetry.memoryUtilizationPercent)) {
        parts.push(formatTelemetryPercent(i18n.t('hardware.gpu.telemetry.memoryUtilization'), telemetry.memoryUtilizationPercent));
    }
    const power = formatTelemetryPower(telemetry);
    if (power) {
        parts.push(power);
    }
    return parts.join(' · ');
};

const normalizeGpuControlTelemetryMap = (source: Readonly<Record<string, GpuControlTelemetry>>): Map<string, GpuControlTelemetry> => {
    const result = new Map<string, GpuControlTelemetry>();
    Object.entries(source).forEach(([deviceId, telemetry]) => {
        const normalized: GpuControlTelemetry = {
            temperatureCelsius: normalizeTelemetryValue(telemetry.temperatureCelsius),
            coreUtilizationPercent: normalizeTelemetryValue(telemetry.coreUtilizationPercent),
            memoryUtilizationPercent: normalizeTelemetryValue(telemetry.memoryUtilizationPercent),
            powerDrawWatts: normalizeTelemetryValue(telemetry.powerDrawWatts),
            powerLimitWatts: normalizeTelemetryValue(telemetry.powerLimitWatts)
        };
        if (hasTelemetry(normalized)) {
            result.set(deviceId, normalized);
        }
    });
    return result;
};

const updateGpuControlTelemetryLabels = (documentRef: Document, telemetryByDeviceId: ReadonlyMap<string, GpuControlTelemetry>): void => {
    const container = dom.resolve('#gpu-controls-container', documentRef);
    if (!(container instanceof HTMLElement)) {
        return;
    }
    const nodes = dom.resolveAll('.gpu-boot-telemetry[data-device-id]', container);
    nodes.forEach((node) => {
        if (!(node instanceof HTMLElement)) {
            return;
        }
        const deviceId = (node.getAttribute('data-device-id') ?? '').trim();
        const label = formatGpuControlTelemetryLabel(telemetryByDeviceId.get(deviceId) ?? null);
        if (node.textContent !== label) {
            node.textContent = label;
        }
        const visible = label.length > 0;
        const severity = resolveGpuControlTelemetryTemperatureSeverity(telemetryByDeviceId.get(deviceId) ?? null);
        node.classList.toggle('gpu-boot-telemetry--hidden', !visible);
        node.classList.toggle('gpu-boot-telemetry--warning', visible && severity === 'warning');
        node.classList.toggle('gpu-boot-telemetry--critical', visible && severity === 'critical');
        node.setAttribute('aria-hidden', visible ? 'false' : 'true');
    });
};

export { formatGpuControlTelemetryLabel, normalizeGpuControlTelemetryMap, resolveGpuControlTelemetryTemperatureSeverity, updateGpuControlTelemetryLabels };
export type { GpuControlTelemetry };

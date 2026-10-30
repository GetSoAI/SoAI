/* SoAI - Hardware page GPU control telemetry controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { GpuControlManagerDependencies } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
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

const resolveGpuControlTelemetryTemperatureSeverity = (telemetry: GpuControlTelemetry | null): TemperatureSeverity => {
    return resolveTemperatureSeverity(telemetry?.temperatureCelsius);
};

type GpuTelemetryMetric = { label: string; value: string; icon: IconName | null; temperature: boolean };

const buildGpuTelemetryMetrics = (telemetry: GpuControlTelemetry | null): GpuTelemetryMetric[] => {
    if (!hasTelemetry(telemetry)) return [];
    const metrics: GpuTelemetryMetric[] = [];
    if (isFiniteNumber(telemetry.temperatureCelsius)) metrics.push({ label: i18n.t('hardware.gpu.telemetry.temperatures'), value: formatTemperature(telemetry.temperatureCelsius, 0), icon: null, temperature: true });
    if (isFiniteNumber(telemetry.coreUtilizationPercent)) metrics.push({ label: i18n.t('hardware.gpu.telemetry.coreUtilization'), value: formatPercent(telemetry.coreUtilizationPercent, 0), icon: 'device-gpu', temperature: false });
    if (isFiniteNumber(telemetry.memoryUtilizationPercent)) metrics.push({ label: i18n.t('hardware.gpu.telemetry.memoryUtilization'), value: formatPercent(telemetry.memoryUtilizationPercent, 0), icon: null, temperature: false });
    if (isFiniteNumber(telemetry.powerDrawWatts) && isFiniteNumber(telemetry.powerLimitWatts) && telemetry.powerLimitWatts > 0) metrics.push({ label: i18n.t('hardware.gpu.telemetry.powerDraw'), value: formatPercent((telemetry.powerDrawWatts / telemetry.powerLimitWatts) * 100, 0), icon: 'zap', temperature: false });
    return metrics;
};

const formatGpuControlTelemetryLabel = (telemetry: GpuControlTelemetry | null, describeTemperature = false): string =>
    buildGpuTelemetryMetrics(telemetry)
        .map((metric) => (metric.temperature && !describeTemperature ? metric.value : `${metric.label} ${metric.value}`))
        .join(' · ');

const renderGpuControlTelemetryMetrics = (telemetry: GpuControlTelemetry | null, getIconSync: GpuControlManagerDependencies['getIconSync']): TrustedHtml =>
    joinUiHtml(
        buildGpuTelemetryMetrics(telemetry).map((metric) => {
            const label = metric.icon ? renderIconSlot(getIconSync(metric.icon, { size: 12, strokeWidth: 1.7 })) : metric.temperature ? EMPTY_UI_HTML : uiText(metric.label);
            return uiHtml`<span class="gpu-telemetry-metric" data-tooltip="${uiAttr(`${metric.label} ${metric.value}`)}">${label}<bdi>${metric.value}</bdi></span>`;
        })
    );

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

const updateGpuControlTelemetryLabels = (documentRef: Document, telemetryByDeviceId: ReadonlyMap<string, GpuControlTelemetry>, getIconSync: GpuControlManagerDependencies['getIconSync']): void => {
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
        const telemetry = telemetryByDeviceId.get(deviceId) ?? null;
        const description = formatGpuControlTelemetryLabel(telemetry, true);
        if (node.getAttribute('aria-label') !== description) {
            const fragment = createHtmlFragment({ documentRef, html: renderGpuControlTelemetryMetrics(telemetry, getIconSync).html, context: node });
            reconcileChildNodes(node, Array.from(fragment.childNodes));
            node.setAttribute('aria-label', description);
        }
        const visible = description.length > 0 && node.closest('.gpu-boot-toggle-row')?.getAttribute('data-content') !== 'boot';
        const severity = resolveGpuControlTelemetryTemperatureSeverity(telemetryByDeviceId.get(deviceId) ?? null);
        node.classList.toggle('gpu-boot-telemetry--hidden', !visible);
        node.classList.toggle('gpu-boot-telemetry--warning', visible && severity === 'warning');
        node.classList.toggle('gpu-boot-telemetry--critical', visible && severity === 'critical');
        node.setAttribute('aria-hidden', visible ? 'false' : 'true');
    });
};

export { renderGpuControlTelemetryMetrics, formatGpuControlTelemetryLabel, normalizeGpuControlTelemetryMap, resolveGpuControlTelemetryTemperatureSeverity, updateGpuControlTelemetryLabels };
export type { GpuControlTelemetry };

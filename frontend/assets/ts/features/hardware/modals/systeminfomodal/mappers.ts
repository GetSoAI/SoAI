/* SoAI - System information modal mapping [frontend/assets/ts/features/hardware/modals/systeminfomodal/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber, formatTemperature } from '@core/localization/public.ts';
import { formatSystemInfoDurationFromMilliseconds } from '@core/primitives/duration.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { resolveHardwareDeviceDisplayName } from '@features/hardware/deviceNames.ts';
import type { SystemInfoFormattingInput } from '@features/hardware/modals/systeminfomodal/types.ts';

const formatHardwareSectionValue = (key: string, value: JsonValue | undefined): string => {
    if (isString(value)) return value;
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return '';
    const normalizedKey = key.toLowerCase();
    if (normalizedKey.includes('bytes')) return formatBytes(numericValue);
    if (normalizedKey.includes('gb')) return `${formatInvariantNumber(numericValue, { maximumFractionDigits: 2 })} GB`;
    if (normalizedKey.includes('celsius') || normalizedKey.includes('temp')) return formatTemperature(numericValue, 1);
    if (normalizedKey.includes('percent') || normalizedKey.includes('usage') || normalizedKey.includes('utilization')) {
        return formatPercent(numericValue);
    }
    return String(numericValue);
};

const addSection = (lines: string[], title: string, entries: Array<[string, string]>): void => {
    if (!entries.length) {
        return;
    }
    lines.push(title, '-'.repeat(title.length));
    for (const [key, value] of entries) {
        lines.push(`${key}: ${value}`);
    }
    lines.push('');
};

const formatPluginLine = (plugin: PluginRecord): string => {
    const name = isString(plugin.displayName) ? plugin.displayName : isString(plugin.name) ? plugin.name : i18n.t('common.unknown');
    const version = isString(plugin.versionSoaiplugin) ? plugin.versionSoaiplugin : null;
    const state = isString(plugin.state) ? plugin.state : null;
    const parts = [name, version ? `${i18n.t('hardware.systemInfo.labels.versionPrefix')}${version}` : null, state ? `${i18n.t('hardware.systemInfo.labels.status')} ${String(state).toUpperCase()}` : null].filter(Boolean);
    return `${i18n.t('hardware.systemInfo.report.bullet')} ${parts.join(', ')}`;
};

export const formatSystemInfo = (input: SystemInfoFormattingInput): string => {
    const titleSystem = i18n.t('hardware.systemInfo.sections.system');
    const titleOs = i18n.t('hardware.systemInfo.sections.os');
    const titleUptime = i18n.t('hardware.systemInfo.sections.uptime');
    const titleSummary = i18n.t('hardware.systemInfo.sections.summary');
    const titleCapabilities = i18n.t('hardware.systemInfo.sections.capabilities');
    const titleCpu = i18n.t('hardware.systemInfo.sections.cpu');
    const titleGpu = i18n.t('hardware.systemInfo.sections.gpu');
    const titleMemory = i18n.t('hardware.systemInfo.sections.memory');
    const titleSwap = i18n.t('hardware.systemInfo.sections.swap');
    const titleNetwork = i18n.t('hardware.systemInfo.sections.network');
    const titleDisk = i18n.t('hardware.systemInfo.sections.disk');
    const titlePlugins = i18n.t('hardware.systemInfo.sections.plugins');
    const titleHealth = i18n.t('hardware.systemInfo.sections.health');

    const separator = i18n.t('hardware.systemInfo.report.separator');
    const lines = [separator, i18n.t('hardware.systemInfo.report.title'), i18n.t('hardware.systemInfo.report.generated', { timestamp: new Date().toISOString() }), separator, ''];

    const systemInfo = input.systemInfo;
    const health = input.health;
    const hardware = input.hardware;
    const pluginList = input.plugins;

    if (systemInfo) {
        const entries = Object.entries(systemInfo)
            .filter(([, value]) => !isNullOrUndefined(value) && !isObject(value))
            .map(([key, value]) => {
                const entry: [string, string] = [key, String(value)];
                return entry;
            });
        addSection(lines, titleSystem, entries);
    }

    const operatingSystem = hardware.os;
    if (operatingSystem) {
        const operatingSystemEntries: Array<[string, string]> = [
            ['system', operatingSystem.system ?? ''],
            ['node_name', operatingSystem.nodeName ?? ''],
            ['release', operatingSystem.release ?? ''],
            ['version', operatingSystem.version ?? ''],
            ['machine', operatingSystem.machine ?? ''],
            ['processor', operatingSystem.processor ?? '']
        ];
        addSection(
            lines,
            titleOs,
            operatingSystemEntries.filter(([, value]) => value.length > 0)
        );
    }

    const uptime = hardware.uptime;
    if (uptime) {
        const uptimeMs = Number(uptime.uptimeMs);
        const bootTimeMs = Number(uptime.bootTimeMs);
        const uptimeEntries: Array<[string, string]> = [
            ['uptime', formatSystemInfoDurationFromMilliseconds(Number.isFinite(uptimeMs) ? uptimeMs : null) ?? ''],
            ['boot_time', Number.isFinite(bootTimeMs) ? new Date(bootTimeMs).toISOString() : '']
        ];
        addSection(
            lines,
            titleUptime,
            uptimeEntries.filter(([, value]) => value.length > 0)
        );
    }

    const summaryEntries: Array<[string, JsonValue | undefined]> = [
        ['total_system_ram_gb', hardware.summary.totalSystemRamGb],
        ['total_vram_gb', hardware.summary.totalVramGb],
        ['total_system_memory_gb', hardware.summary.totalSystemMemoryGb]
    ];
    addSection(
        lines,
        titleSummary,
        summaryEntries.filter((entry): entry is [string, JsonValue] => !isNullOrUndefined(entry[1])).map(([key, value]) => [key, formatHardwareSectionValue(key, value)])
    );

    const capabilityEntries: Array<[string, JsonValue | undefined]> = [
        ['platform', hardware.capabilities.platform],
        ['system_ram_gb', hardware.capabilities.systemRamGb],
        ['total_vram_gb', hardware.capabilities.totalVramGb],
        ['total_system_memory_gb', hardware.capabilities.totalSystemMemoryGb],
        ['monitoring_interval_ms', hardware.capabilities.monitoringIntervalMs],
        ['history_retention_hours', hardware.capabilities.historyRetentionHours]
    ];
    addSection(
        lines,
        titleCapabilities,
        capabilityEntries.filter((entry): entry is [string, JsonValue] => !isNullOrUndefined(entry[1])).map(([key, value]) => [key, formatHardwareSectionValue(key, value)])
    );

    const cpus = hardware.cpus ?? [];
    if (cpus.length) {
        const cpuLines: Array<[string, string]> = [];
        cpus.forEach((cpu, index) => {
            const name = resolveHardwareDeviceDisplayName(cpu) ?? '';
            const cpuLabel = cpus.length > 1 ? i18n.t('hardware.systemInfo.sections.cpuEntryWithIndex', { index, name: name || i18n.t('common.unknown') }) : i18n.t('hardware.systemInfo.sections.cpuEntry', { name: name || i18n.t('common.unknown') });
            const usage = formatHardwareSectionValue('usage_percent', cpu.usagePercent);
            const temp = formatHardwareSectionValue('temperature_celsius', cpu.temperatureCelsius);
            cpuLines.push([cpuLabel, [usage ? `usage=${usage}` : null, temp ? `temp=${temp}` : null].filter(Boolean).join(' , ')]);
        });
        addSection(lines, titleCpu, cpuLines);
    }

    const memory = hardware.memory;
    if (memory) {
        const values: Array<[string, JsonValue | undefined]> = [
            ['total_bytes', memory.totalBytes],
            ['used_bytes', memory.usedBytes],
            ['free_bytes', memory.freeBytes],
            ['percent_used', memory.percentUsed]
        ];
        const entries = values.filter((entry): entry is [string, JsonValue] => !isNullOrUndefined(entry[1])).map(([key, value]): [string, string] => [key, formatHardwareSectionValue(key, value)]);
        addSection(lines, titleMemory, entries);
    }

    const swap = hardware.swap;
    if (swap) {
        const values: Array<[string, JsonValue | undefined]> = [
            ['total_bytes', swap.totalBytes],
            ['used_bytes', swap.usedBytes],
            ['free_bytes', swap.freeBytes],
            ['percent_used', swap.percentUsed]
        ];
        const entries = values.filter((entry): entry is [string, JsonValue] => !isNullOrUndefined(entry[1])).map(([key, value]): [string, string] => [key, formatHardwareSectionValue(key, value)]);
        addSection(lines, titleSwap, entries);
    }

    const gpus = hardware.gpu?.gpus ?? [];
    if (gpus.length) {
        const gpuLines: Array<[string, string]> = [];
        gpus.forEach((gpuEntry, index) => {
            const name = resolveHardwareDeviceDisplayName(gpuEntry) ?? '';
            const gpuLabel = i18n.t('hardware.systemInfo.sections.gpuEntry', { index, name: name || i18n.t('common.unknown') });
            const utilization = formatHardwareSectionValue('utilization', gpuEntry.utilization);
            const memory = formatHardwareSectionValue('percent_used', gpuEntry.percentUsed);
            const temp = formatHardwareSectionValue('temperature', gpuEntry.temperature);
            gpuLines.push([gpuLabel, [utilization ? `util=${utilization}` : null, memory ? `mem=${memory}` : null, temp ? `temp=${temp}` : null].filter(Boolean).join(' , ')]);
        });
        addSection(lines, titleGpu, gpuLines);
    }

    const netInterfaces = hardware.network?.interfaces ?? [];
    if (netInterfaces.length) {
        const ifaceLines: Array<[string, string]> = [];
        netInterfaces.forEach((iface, index) => {
            const name = isString(iface.name) ? iface.name : '';
            const ifaceLabel = name ? i18n.t('hardware.systemInfo.sections.networkEntryNamed', { name }) : i18n.t('hardware.systemInfo.sections.networkEntryIndexed', { index });
            const mac = isString(iface.macAddress) ? iface.macAddress : '';
            ifaceLines.push([ifaceLabel, mac ? `mac=${mac}` : '']);
        });
        addSection(lines, titleNetwork, ifaceLines);
    }

    const disks = hardware.disk ?? [];
    if (disks.length) {
        const diskLines: Array<[string, string]> = [];
        disks.forEach((disk, index) => {
            const mount = isString(disk.mount) ? disk.mount : '';
            const diskLabel = mount ? i18n.t('hardware.systemInfo.sections.diskEntryMounted', { mount }) : i18n.t('hardware.systemInfo.sections.diskEntryIndexed', { index });
            const percentUsed = formatHardwareSectionValue('percent_used', disk.percentUsed);
            diskLines.push([diskLabel, percentUsed ? `used=${percentUsed}` : '']);
        });
        addSection(lines, titleDisk, diskLines);
    }

    if (pluginList.length) {
        const pluginLines = pluginList.map((plugin) => formatPluginLine(plugin));
        lines.push(titlePlugins, '-'.repeat(titlePlugins.length), ...pluginLines, '');
    }

    if (health) {
        const healthLines: Array<[string, string]> = [];
        for (const [key, value] of Object.entries(health)) {
            if (!isNullOrUndefined(value) && !isObject(value)) {
                healthLines.push([key, String(value)]);
            }
        }
        addSection(lines, titleHealth, healthLines);
    }

    lines.push(separator, i18n.t('hardware.systemInfo.report.end'), separator);
    return lines.join('\n');
};

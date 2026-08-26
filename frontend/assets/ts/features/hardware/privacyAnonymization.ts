/* SoAI - Hardware feature privacy anonymization [frontend/assets/ts/features/hardware/privacyAnonymization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeDiskMountPath } from '@features/hardware/privacyDiskMounts.ts';
import { protectSoAIInstallPaths, restoreSoAIInstallPaths } from '@features/hardware/privacyInstallPaths.ts';

interface PrivacyPatterns {
    deviceIdPrefix: RegExp;
    uuid: RegExp;
    email: RegExp;
    urlCredentials: RegExp;
    urlSensitiveQueryValue: RegExp;
    ipv4: RegExp;
    ipv6: RegExp;
    macAddress: RegExp;
    pciBusAddress: RegExp;
    isoTimestamp: RegExp;
    uptimeValue: RegExp;
    diskMountLine: RegExp;
    hostnameValue: RegExp;
    sensitiveKeyValue: RegExp;
    linuxHomePath: RegExp;
    macHomePath: RegExp;
    windowsHomePath: RegExp;
    windowsUncPath: RegExp;
    runtimeUserPath: RegExp;
    mountPath: RegExp;
    mediaPath: RegExp;
    mediaUserPath: RegExp;
    volumesPath: RegExp;
    dockerNetworkNamespace: RegExp;
    virtualNetworkInterface: RegExp;
    longHexIdentifier: RegExp;
}

const PRIVACY_PATTERNS: Readonly<PrivacyPatterns> = Object.freeze({
    deviceIdPrefix: /\b(disk|gpu|nic|cpu|nvidia|GPU)([-:])([a-f0-9][a-f0-9._:-]{7,})\b/gi,
    uuid: /\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b/g,
    email: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
    urlCredentials: /\b([A-Za-z][A-Za-z0-9+.-]*:\/\/)([^/@\s]+)@/g,
    urlSensitiveQueryValue: /([?&](?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret|token)=)([^&#\s]+)/gi,
    ipv4: /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/g,
    ipv6: /\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b|::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b/gi,
    macAddress: /\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b/g,
    pciBusAddress: /\b(?:0000:)?[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]\b/g,
    isoTimestamp: /(\d{4}-\d{2}-\d{2}T\d{2}:)(\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?/g,
    uptimeValue: /\b(uptime)\b(\s*[:=]\s*)([^\r\n]+)/gi,
    diskMountLine: /^(\s*(?:DISK|DISCO) \()([^)]+)(\):)/gm,
    hostnameValue: /\b(node_name|hostname|host_name|computer_name)\b(\s*[:=]\s*)([^\r\n,]+)/gi,
    sensitiveKeyValue: /\b(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|device[_-]?id|disk[_-]?id|gpu[_-]?id|host[_-]?id|license[_-]?key|machine[_-]?id|nic[_-]?id|password|passwd|product[_-]?uuid|secret|serial(?:[_-]?number)?|token)\b(\s*[:=]\s*)([^\s,]+)/gi,
    linuxHomePath: /(\B\/home\/)([^/\s:)]+)/g,
    macHomePath: /(\B\/Users\/)([^/\s:)]+)/g,
    windowsHomePath: /\b([A-Za-z]:\\Users\\)([^\\\s:)]+)/g,
    windowsUncPath: /\\\\[^\\\s:)]+\\[^\\\s:)]+/g,
    runtimeUserPath: /(\B\/run\/user\/)(\d+)/g,
    mountPath: /(\B\/mnt\/)([^\s:)]+)/g,
    mediaPath: /(\B\/media\/)([^/\s:)]+)(\/)([^\s:)]+)/g,
    mediaUserPath: /(\B\/media\/)([^\s:)]+)/g,
    volumesPath: /(\B\/Volumes\/)([^\s:)]+)/g,
    dockerNetworkNamespace: /(\B\/run\/docker\/netns\/)([A-Za-z0-9._-]+)/g,
    virtualNetworkInterface: /\b(br-|veth)([0-9a-fA-F]{6,32})\b/g,
    longHexIdentifier: /\b[0-9a-fA-F]{12,64}\b/g
});

const STRUCTURE_DELIMITERS: Readonly<string[]> = Object.freeze(['-', ':', '.', '/', '\\']);
const REDACTED_CREDENTIALS = '[credentials]';
const REDACTED_EMAIL = '[email]';
const REDACTED_HOSTNAME = '[hostname]';
const REDACTED_MOUNT = '[mount]';
const REDACTED_NETNS = '[netns]';
const REDACTED_USER = '[user]';
const REDACTED_VOLUME = '[volume]';

const getRandomPreserveRatio = (): number => 0.35 + Math.random() * 0.2;

const shuffleIndices = (indices: readonly number[]): number[] => {
    const shuffled = [...indices];
    for (let index = shuffled.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(Math.random() * (index + 1));
        const currentValue = shuffled[index];
        const swapValue = shuffled[swapIndex];
        if (currentValue === undefined || swapValue === undefined) {
            throw new Error('shuffleIndices requires in-bounds indices');
        }
        shuffled[index] = swapValue;
        shuffled[swapIndex] = currentValue;
    }
    return shuffled;
};

const maskPreservingStructure = (text: string, preserveRatio: number): string => {
    if (!Number.isFinite(preserveRatio) || preserveRatio < 0 || preserveRatio > 1) {
        throw new RangeError('maskPreservingStructure preserveRatio must be a finite number between 0 and 1');
    }
    if (text.length === 0) return text;
    const chars = text.split('');
    const alphanumericIndices: number[] = [];
    chars.forEach((char, index) => {
        if (/[0-9a-fA-F]/.test(char)) {
            alphanumericIndices.push(index);
        }
    });
    if (alphanumericIndices.length === 0) {
        return text;
    }
    const preserveCount = Math.max(1, Math.round(alphanumericIndices.length * preserveRatio));
    const shuffled = shuffleIndices(alphanumericIndices);
    const toPreserve = new Set(shuffled.slice(0, preserveCount));
    return chars
        .map((char, index) => {
            if (STRUCTURE_DELIMITERS.includes(char)) {
                return char;
            }
            if (/[0-9a-fA-F]/.test(char) && !toPreserve.has(index)) {
                return '#';
            }
            return char;
        })
        .join('');
};

const anonymizeTimestamp = (_match: string, prefix: string, time: string, ms: string | undefined, tz: string | undefined): string => {
    const maskedTime = time.replace(/[0-9]/g, '#');
    const maskedMs = ms ? ms.replace(/[0-9]/g, '#') : '';
    return `${prefix}${maskedTime}${maskedMs}${tz || ''}`;
};

const maskSensitiveCharacters = (text: string): string => text.replace(/[A-Za-z0-9]/g, '#');

const maskDigits = (text: string): string => text.replace(/[0-9]/g, '#');

const replaceDeviceId = (_match: string, prefix: string, separator: string, id: string): string => `${prefix}${separator}${maskSensitiveCharacters(id)}`;

const replaceQueryValue = (_match: string, prefix: string, value: string): string => `${prefix}${maskSensitiveCharacters(value)}`;

const replaceHostnameValue = (_match: string, key: string, separator: string): string => `${key}${separator}${REDACTED_HOSTNAME}`;

const replaceSensitiveKeyValue = (_match: string, key: string, separator: string, value: string): string => `${key}${separator}${maskSensitiveCharacters(value)}`;

const replacePrefixedValue = (_match: string, prefix: string, value: string): string => `${prefix}${maskSensitiveCharacters(value)}`;

const replaceUptimeValue = (_match: string, key: string, separator: string, value: string): string => `${key}${separator}${value.replace(/\b(\d+)(m|s)\b/g, (_durationMatch: string, digits: string, unit: string) => `${maskDigits(digits)}${unit}`)}`;

const replaceDiskMountLine = (_match: string, prefix: string, mountPath: string, suffix: string): string => `${prefix}${normalizeDiskMountPath(mountPath)}${suffix}`;

const replaceHomePath = (_match: string, prefix: string): string => `${prefix}${REDACTED_USER}`;

const replaceWindowsUncPath = (): string => '\\\\[server]\\[share]';

const replaceRuntimeUserPath = (_match: string, prefix: string, userId: string): string => `${prefix}${maskDigits(userId)}`;

const replaceMountPath = (_match: string, prefix: string): string => `${prefix}${REDACTED_MOUNT}`;

const replaceMediaPath = (_match: string, prefix: string, _user: string, separator: string): string => `${prefix}${REDACTED_USER}${separator}${REDACTED_VOLUME}`;

const replaceVolumePath = (_match: string, prefix: string): string => `${prefix}${REDACTED_VOLUME}`;

const replaceDockerNetworkNamespace = (_match: string, prefix: string): string => `${prefix}${REDACTED_NETNS}`;

const anonymizeSystemInfoText = (text: string): string => {
    const protectedInput = protectSoAIInstallPaths(text);
    let result = protectedInput.text;
    result = result.replace(PRIVACY_PATTERNS.urlCredentials, (_match, scheme: string) => `${scheme}${REDACTED_CREDENTIALS}@`);
    result = result.replace(PRIVACY_PATTERNS.urlSensitiveQueryValue, replaceQueryValue);
    result = result.replace(PRIVACY_PATTERNS.email, REDACTED_EMAIL);
    result = result.replace(PRIVACY_PATTERNS.uptimeValue, replaceUptimeValue);
    result = result.replace(PRIVACY_PATTERNS.diskMountLine, replaceDiskMountLine);
    result = result.replace(PRIVACY_PATTERNS.hostnameValue, replaceHostnameValue);
    result = result.replace(PRIVACY_PATTERNS.sensitiveKeyValue, replaceSensitiveKeyValue);
    result = result.replace(PRIVACY_PATTERNS.linuxHomePath, replaceHomePath);
    result = result.replace(PRIVACY_PATTERNS.macHomePath, replaceHomePath);
    result = result.replace(PRIVACY_PATTERNS.windowsHomePath, replaceHomePath);
    result = result.replace(PRIVACY_PATTERNS.windowsUncPath, replaceWindowsUncPath);
    result = result.replace(PRIVACY_PATTERNS.runtimeUserPath, replaceRuntimeUserPath);
    result = result.replace(PRIVACY_PATTERNS.dockerNetworkNamespace, replaceDockerNetworkNamespace);
    result = result.replace(PRIVACY_PATTERNS.mediaPath, replaceMediaPath);
    result = result.replace(PRIVACY_PATTERNS.mediaUserPath, replaceHomePath);
    result = result.replace(PRIVACY_PATTERNS.mountPath, replaceMountPath);
    result = result.replace(PRIVACY_PATTERNS.volumesPath, replaceVolumePath);
    result = result.replace(PRIVACY_PATTERNS.virtualNetworkInterface, replacePrefixedValue);
    result = result.replace(PRIVACY_PATTERNS.deviceIdPrefix, replaceDeviceId);
    result = result.replace(PRIVACY_PATTERNS.uuid, maskSensitiveCharacters);
    result = result.replace(PRIVACY_PATTERNS.macAddress, maskSensitiveCharacters);
    result = result.replace(PRIVACY_PATTERNS.pciBusAddress, maskSensitiveCharacters);
    result = result.replace(PRIVACY_PATTERNS.ipv4, maskDigits);
    result = result.replace(PRIVACY_PATTERNS.ipv6, maskSensitiveCharacters);
    result = result.replace(PRIVACY_PATTERNS.longHexIdentifier, maskSensitiveCharacters);
    result = result.replace(PRIVACY_PATTERNS.isoTimestamp, anonymizeTimestamp);
    return restoreSoAIInstallPaths(result, protectedInput.paths);
};

export { PRIVACY_PATTERNS, STRUCTURE_DELIMITERS, getRandomPreserveRatio, maskPreservingStructure, anonymizeTimestamp, anonymizeSystemInfoText };
export type { PrivacyPatterns };

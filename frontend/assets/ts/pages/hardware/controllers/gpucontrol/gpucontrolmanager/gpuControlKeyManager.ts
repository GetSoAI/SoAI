/* SoAI - GPU control key management [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlKeyManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isSafeKeyChar = (char: string): boolean => {
    const code = char.charCodeAt(0);
    return (code >= 48 && code <= 57) || (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || char === '_' || char === '-';
};

const appendUniqueKey = (target: string[], key: string): void => {
    if (key && !target.includes(key)) {
        target.push(key);
    }
};

export const buildGpuControlKey = (deviceId: string | null, defaultKey: string): string => {
    const source = deviceId && deviceId.trim() ? deviceId.trim() : defaultKey;
    let output = '';
    for (let index = 0; index < source.length; index += 1) {
        const char = source.charAt(index);
        output += isSafeKeyChar(char) ? char : `_x${source.charCodeAt(index).toString(16)}_`;
    }
    return output || defaultKey;
};

export const collectGpuControlLookupKeys = ({ deviceId, sourceKey, gpuIndex }: { deviceId: string | null; sourceKey: string; gpuIndex: number | null }): string[] => {
    const lookupKeys: string[] = [];
    if (deviceId) {
        appendUniqueKey(lookupKeys, buildGpuControlKey(deviceId, sourceKey));
    }
    if (gpuIndex !== null) {
        appendUniqueKey(lookupKeys, String(gpuIndex));
    }
    appendUniqueKey(lookupKeys, buildGpuControlKey(null, sourceKey));
    return lookupKeys;
};

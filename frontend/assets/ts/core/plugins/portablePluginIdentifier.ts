/* SoAI - Portable V1 plugin identifier validation [frontend/assets/ts/core/plugins/portablePluginIdentifier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const PORTABLE_PLUGIN_IDENTIFIER = /^[a-z0-9](?:[a-z0-9_-]{0,99})$/;
const WINDOWS_RESERVED_BASENAMES: ReadonlySet<string> = Object.freeze(new Set(['con', 'prn', 'aux', 'nul', 'clock$', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']));

const isPortablePluginIdentifier = (value: string): boolean => {
    if (!PORTABLE_PLUGIN_IDENTIFIER.test(value)) return false;
    return !WINDOWS_RESERVED_BASENAMES.has(value);
};

const requirePortablePluginIdentifier = (value: string, label = 'Plugin identifier'): string => {
    const normalized = value.trim();
    if (!isPortablePluginIdentifier(normalized)) {
        throw new Error(`${label} must use lowercase ASCII letters, numbers, dashes, or underscores and be portable across filesystems`);
    }
    return normalized;
};

export { isPortablePluginIdentifier, requirePortablePluginIdentifier };

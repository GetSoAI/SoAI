/* SoAI - Shared frontend file path resolution [frontend/assets/ts/core/filePathResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const isAbsoluteFilesystemPath = (value: string): boolean => {
    const normalizedValue = value.trim();
    return /^[a-zA-Z]:[\\/]/.test(normalizedValue) || normalizedValue.startsWith('/') || normalizedValue.startsWith('\\\\') || normalizedValue.startsWith('//');
};

const getFilesystemParentPath = (value: string): string => {
    const normalizedValue = value.replace(/[\\/]+$/, '');
    const lastForwardSlashIndex = normalizedValue.lastIndexOf('/');
    const lastBackwardSlashIndex = normalizedValue.lastIndexOf('\\');
    const lastSeparatorIndex = Math.max(lastForwardSlashIndex, lastBackwardSlashIndex);
    if (lastSeparatorIndex < 0) {
        return '';
    }
    if (lastSeparatorIndex === 0) {
        return normalizedValue[0] === '\\' && normalizedValue[1] === '\\' ? normalizedValue : normalizedValue.slice(0, 1);
    }
    return normalizedValue.slice(0, lastSeparatorIndex);
};

const resolveAbsoluteFilesystemPath = <TBasePath, TPath>(basePath: TBasePath, path: TPath): string => {
    const normalizedBasePath = toTrimmedString(basePath);
    const normalizedPath = toTrimmedString(path);

    if (!normalizedPath) {
        return normalizedBasePath;
    }
    if (isAbsoluteFilesystemPath(normalizedPath)) {
        return normalizedPath;
    }
    if (!normalizedBasePath) {
        return normalizedPath;
    }

    const trimmedBasePath = normalizedBasePath.replace(/[\\/]+$/, '');
    const trimmedPath = normalizedPath.replace(/^[\\/]+/, '');
    const separator = trimmedBasePath.includes('\\') && !trimmedBasePath.includes('/') ? '\\' : '/';
    return `${trimmedBasePath}${separator}${trimmedPath}`;
};

const resolveConfigManagedFilesystemPath = <TBasePath, TSystemDataPath, TConfiguredPath>(options: { basePath: TBasePath; systemDataPath: TSystemDataPath; configuredPath: TConfiguredPath; layout: 'base' | 'state' }): string => {
    const normalizedConfiguredPath = toTrimmedString(options.configuredPath);
    if (!normalizedConfiguredPath) {
        return '';
    }
    if (isAbsoluteFilesystemPath(normalizedConfiguredPath)) {
        return normalizedConfiguredPath;
    }

    const normalizedBasePath = toTrimmedString(options.basePath);
    const normalizedSystemDataPath = toTrimmedString(options.systemDataPath);
    const absoluteBasePath = isAbsoluteFilesystemPath(normalizedBasePath) ? normalizedBasePath : '';
    const absoluteSystemDataPath = isAbsoluteFilesystemPath(normalizedSystemDataPath) ? normalizedSystemDataPath : '';

    if (options.layout === 'state') {
        if (absoluteSystemDataPath) {
            return resolveAbsoluteFilesystemPath(absoluteSystemDataPath, normalizedConfiguredPath);
        }
        if (absoluteBasePath) {
            const resolvedSystemDataPath = normalizedSystemDataPath ? resolveAbsoluteFilesystemPath(absoluteBasePath, normalizedSystemDataPath) : resolveAbsoluteFilesystemPath(absoluteBasePath, 'data');
            return resolveAbsoluteFilesystemPath(resolvedSystemDataPath, normalizedConfiguredPath);
        }
        return normalizedConfiguredPath;
    }

    if (absoluteBasePath) {
        return resolveAbsoluteFilesystemPath(absoluteBasePath, normalizedConfiguredPath);
    }
    if (absoluteSystemDataPath) {
        const derivedBasePath = getFilesystemParentPath(absoluteSystemDataPath);
        return derivedBasePath ? resolveAbsoluteFilesystemPath(derivedBasePath, normalizedConfiguredPath) : normalizedConfiguredPath;
    }
    return normalizedConfiguredPath;
};

const normalizePathLeafSource = <T>(value: T): string => {
    const trimmed = toTrimmedString(value);
    return trimmed.replace(/\\/g, '/');
};

const normalizeUrlPathLeafSource = <T>(value: T): string => {
    const trimmed = toTrimmedString(value);
    const withoutQuery = trimmed.split('?', 1)[0] ?? '';
    return withoutQuery.split('#', 1)[0]?.replace(/\\/g, '/') ?? '';
};

const resolvePathLeaf = <T>(value: T): string => {
    const normalized = normalizePathLeafSource(value);
    if (!normalized) {
        return '';
    }
    const segments = normalized.split('/').filter((segment) => segment.trim().length > 0);
    return segments.length > 0 ? (segments[segments.length - 1] ?? '').trim() : '';
};

const resolveUrlPathLeaf = <T>(value: T): string => {
    const normalized = normalizeUrlPathLeafSource(value);
    if (!normalized) {
        return '';
    }
    const segments = normalized.split('/').filter((segment) => segment.trim().length > 0);
    return segments.length > 0 ? (segments[segments.length - 1] ?? '').trim() : '';
};

const requirePathLeaf = <T>(value: T, errorMessage: string): string => {
    const leaf = resolvePathLeaf(value);
    if (!leaf) {
        throw new Error(errorMessage);
    }
    return leaf;
};

const resolveLeafExtension = (leaf: string): string | null => {
    if (!leaf) {
        return null;
    }
    const dotIndex = leaf.lastIndexOf('.');
    if (dotIndex < 0 || dotIndex >= leaf.length - 1) {
        return null;
    }
    const extension = leaf.slice(dotIndex + 1).trim();
    return extension || null;
};

const resolveUrlPathExtension = <T>(value: T): string | null => {
    return resolveLeafExtension(resolveUrlPathLeaf(value));
};

export { isAbsoluteFilesystemPath, requirePathLeaf, resolveAbsoluteFilesystemPath, resolveConfigManagedFilesystemPath, resolvePathLeaf, resolveUrlPathExtension };

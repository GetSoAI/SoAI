/* SoAI - Shared file explorer browser paths [frontend/assets/ts/core/fileexplorerbrowser/paths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const toVirtualPath = (value: string): string => {
    const trimmed = value.trim();
    const withRoot = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    const collapsed = withRoot.replace(/\/{2,}/g, '/');
    if (collapsed === '') {
        return '/';
    }
    return collapsed.length > 1 && collapsed.endsWith('/') ? collapsed.slice(0, -1) : collapsed;
};

const isAbsoluteOsPath = (value: string): boolean => {
    const trimmed = value.trim();
    if (!trimmed) {
        return false;
    }
    if (trimmed.startsWith('/')) {
        return true;
    }
    if (trimmed.startsWith('\\\\') || trimmed.startsWith('//')) {
        return true;
    }
    return /^[A-Za-z]:[\\/]/.test(trimmed);
};

const joinVirtualPath = (parentPath: string, childName: string): string => {
    const base = toVirtualPath(parentPath);
    return toVirtualPath(base === '/' ? `/${childName}` : `${base}/${childName}`);
};

const parentVirtualPath = (path: string): string => {
    const normalized = toVirtualPath(path);
    if (normalized === '/') {
        return '/';
    }
    const parts = normalized.split('/').filter(Boolean);
    parts.pop();
    return parts.length > 0 ? `/${parts.join('/')}` : '/';
};

const basenameVirtualPath = (path: string): string => {
    const normalized = toVirtualPath(path);
    if (normalized === '/') {
        return '/';
    }
    const parts = normalized.split('/').filter(Boolean);
    return parts[parts.length - 1] ?? '/';
};

const isWindowsLikePath = (value: string): boolean => {
    const trimmed = value.trim();
    if (!trimmed) {
        return false;
    }
    if (trimmed.includes('\\')) {
        return true;
    }
    if (/^[A-Za-z]:/.test(trimmed)) {
        return true;
    }
    return trimmed.startsWith('//');
};

const normalizeOsPathForComparison = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        return '';
    }
    const replaced = trimmed.replace(/\\/g, '/');
    if (replaced.startsWith('//')) {
        const rest = replaced.slice(2).replace(/\/{2,}/g, '/');
        return `//${rest}`;
    }
    return replaced.replace(/\/{2,}/g, '/');
};

const stripTrailingForwardSlashes = (value: string): string => {
    if (value === '/' || value === '') {
        return value;
    }
    if (/^[A-Za-z]:\/?$/.test(value)) {
        return value;
    }
    return value.replace(/\/+$/g, '');
};

const stripTrailingSeparator = (value: string, separator: '\\' | '/'): string => {
    if (!value) {
        return value;
    }
    if (separator === '/') {
        return stripTrailingForwardSlashes(value);
    }
    const trimmed = value.trimEnd();
    if (trimmed === '\\\\') {
        return trimmed;
    }
    if (/^[A-Za-z]:\\\\$/.test(trimmed)) {
        return trimmed.slice(0, 2);
    }
    return trimmed.replace(/\\+$/g, '');
};

const resolveAbsolutePath = (rootPathResolved: string | null, virtualPath: string): string | null => {
    if (!rootPathResolved) {
        return null;
    }
    const rootTrimmed = rootPathResolved.trim();
    if (!rootTrimmed) {
        return null;
    }
    const normalizedVirtual = toVirtualPath(virtualPath);
    if (rootTrimmed === '/' && normalizedVirtual.startsWith('/')) {
        return normalizedVirtual;
    }
    if (normalizedVirtual === '/') {
        return rootTrimmed;
    }
    const separator: '\\' | '/' = isWindowsLikePath(rootTrimmed) ? '\\' : '/';
    const rootBase = stripTrailingSeparator(rootTrimmed, separator);
    const remainder = normalizedVirtual.slice(1).replace(/\//g, separator);
    return `${rootBase}${separator}${remainder}`;
};

const resolveVirtualPathFromAbsolute = (rootPathResolved: string, absolutePath: string): string | null => {
    const trimmedAbsolute = absolutePath.trim();
    if (!trimmedAbsolute || !isAbsoluteOsPath(trimmedAbsolute)) {
        return null;
    }
    const rootComparable = normalizeOsPathForComparison(rootPathResolved);
    const absoluteComparable = normalizeOsPathForComparison(trimmedAbsolute);
    if (!rootComparable) {
        return null;
    }
    const windowsLike = isWindowsLikePath(rootPathResolved);
    const compareRoot = windowsLike ? rootComparable.toLowerCase() : rootComparable;
    const compareAbs = windowsLike ? absoluteComparable.toLowerCase() : absoluteComparable;
    if (compareRoot === '/') {
        return compareAbs.startsWith('/') ? toVirtualPath(absoluteComparable) : null;
    }
    const rootNoTrailing = stripTrailingForwardSlashes(compareRoot);
    if (compareAbs === rootNoTrailing) {
        return '/';
    }
    const prefix = rootNoTrailing.endsWith('/') ? rootNoTrailing : `${rootNoTrailing}/`;
    if (!compareAbs.startsWith(prefix)) {
        return null;
    }
    return toVirtualPath(absoluteComparable.slice(prefix.length));
};

const resolveFileBrowserEnteredPath = (rootPathResolved: string | null, enteredPath: string): string | null => {
    const trimmedPath = enteredPath.trim();
    if (!trimmedPath) {
        return null;
    }
    if (rootPathResolved) {
        const virtualPath = resolveVirtualPathFromAbsolute(rootPathResolved, trimmedPath);
        if (virtualPath !== null) {
            return virtualPath;
        }
        if (isWindowsLikePath(trimmedPath)) {
            return null;
        }
    }
    return toVirtualPath(trimmedPath);
};

export { basenameVirtualPath, isAbsoluteOsPath, joinVirtualPath, parentVirtualPath, resolveAbsolutePath, resolveFileBrowserEnteredPath, resolveVirtualPathFromAbsolute, toVirtualPath };

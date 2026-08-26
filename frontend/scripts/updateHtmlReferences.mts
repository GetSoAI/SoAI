/* SoAI - Built asset reference synchronization for frontend HTML [frontend/scripts/updateHtmlReferences.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isVerbose = process.env.SOAI_BUILD_VERBOSE === '1';
const log = (...args: readonly (string | number | boolean | null | undefined)[]) => {
    if (isVerbose) {
        console.log(...args);
    }
};

interface ManifestEntry {
    file: string;
    name?: string;
    src?: string;
    isEntry?: boolean;
    css?: string[];
}

interface Manifest {
    [key: string]: ManifestEntry;
}

const frontendRoot = process.env.SOAI_FRONTEND_BUILD_ROOT ? resolve(process.env.SOAI_FRONTEND_BUILD_ROOT) : resolve(__dirname, '..');
const manifestPath = resolve(frontendRoot, 'assets/build/manifest.json');
const indexPath = resolve(frontendRoot, 'index.html');
const detachedPath = resolve(frontendRoot, 'detached.html');

const manifest: Manifest = JSON.parse(readFileSync(manifestPath, 'utf-8'));

const getCriticalJs = (): string => {
    const entry = Object.values(manifest).find((e) => e.isEntry && e.name === 'critical');
    if (!entry?.file) {
        throw new Error('Could not determine bundled critical entry from Vite manifest (expected entry name: critical).');
    }
    return `./assets/build/${entry.file}`;
};

const getMainJs = (): string => {
    const entry = Object.values(manifest).find((e) => e.isEntry && e.name === 'main');
    if (!entry?.file) {
        throw new Error('Could not determine bundled main entry from Vite manifest (expected entry name: main).');
    }
    return `./assets/build/${entry.file}`;
};

const getDetachedJs = (): string => {
    const entry = Object.values(manifest).find((e) => e.isEntry && e.name === 'detached');
    if (!entry?.file) {
        throw new Error('Could not determine bundled detached entry from Vite manifest (expected entry name: detached).');
    }
    return `./assets/build/${entry.file}`;
};

const getStyleCss = (): string => {
    const entry = manifest['style.css'];
    if (entry?.file) {
        return `./assets/build/${entry.file}`;
    }
    const mainEntry = Object.values(manifest).find((e) => e.isEntry && e.name === 'main');
    const cssFile = mainEntry?.css?.[0];
    if (cssFile) {
        return `./assets/build/${cssFile}`;
    }
    throw new Error('Could not determine bundled CSS file from Vite manifest');
};

const replaceOrThrow = (source: string, pattern: RegExp, replacement: string, label: string): string => {
    if (!pattern.test(source)) {
        throw new Error(`Could not update ${label} reference. Pattern not found.`);
    }
    pattern.lastIndex = 0;
    return source.replace(pattern, replacement);
};

const leadingPathPattern = '(?:/|\\.\\/)?';

const CSS_BOOT_PATTERN = new RegExp(`(\\s*)<link rel="stylesheet" href="${leadingPathPattern}assets/css/boot\\.css" />`);

const CSS_MAIN_PATTERN = new RegExp(`(\\s*)<link rel="stylesheet" href="(?:${leadingPathPattern}assets/build/css/[^"]+\\.css)?" />`);
const CSS_DETACHED_PATTERN = new RegExp(`(\\s*)<link rel="stylesheet" href="(?:${leadingPathPattern}assets/build/css/[^"]+\\.css)?" />`);
const CRITICAL_PATTERN = new RegExp(`(\\s*)(?:<script type="module" src="${leadingPathPattern}assets/ts/critical/themeInit\\.js"></script>\\s*<script type="module" src="${leadingPathPattern}assets/ts/critical/preloaderLogo\\.js"></script>\\s*<script type="module" src="${leadingPathPattern}assets/ts/critical/windowIdentity\\.js"></script>\\s*<script type="module" src="${leadingPathPattern}assets/ts/critical/diagnostics\\.js"></script>|<script type="module" src="${leadingPathPattern}assets/build/js/critical-[^"]+\\.js"></script>)`, 's');
const MAIN_ENTRY_PATTERN = new RegExp(`(\\s*)<script type="module" src="${leadingPathPattern}assets/build/js/main-[^"]+\\.js"(?:\\s+data-soai-entry="main")?\\s*></script>`);
const DETACHED_ENTRY_PATTERN = new RegExp(`(\\s*)<script type="module" src="${leadingPathPattern}assets/build/js/detached-[^"]+\\.js"(?:\\s+data-soai-entry="detached")?\\s*></script>`);

const updateIndexHtml = (): void => {
    let html = readFileSync(indexPath, 'utf-8');

    html = replaceOrThrow(html, CSS_BOOT_PATTERN, `$1<link rel="stylesheet" href="./assets/css/boot.css" />`, 'index.html boot CSS');

    html = replaceOrThrow(html, CSS_MAIN_PATTERN, `$1<link rel="stylesheet" href="${getStyleCss()}" />`, 'index.html CSS');

    html = replaceOrThrow(html, CRITICAL_PATTERN, `$1<script type="module" src="${getCriticalJs()}"></script>`, 'index.html critical script');

    html = replaceOrThrow(html, MAIN_ENTRY_PATTERN, `$1<script type="module" src="${getMainJs()}" data-soai-entry="main"></script>`, 'index.html main entry');

    writeFileSync(indexPath, html, 'utf-8');
    log('Updated index.html');
};

const updateDetachedHtml = (): void => {
    let html = readFileSync(detachedPath, 'utf-8');

    html = replaceOrThrow(html, CSS_BOOT_PATTERN, `$1<link rel="stylesheet" href="./assets/css/boot.css" />`, 'detached.html boot CSS');

    html = replaceOrThrow(html, CSS_DETACHED_PATTERN, `$1<link rel="stylesheet" href="${getStyleCss()}" />`, 'detached.html CSS');

    html = replaceOrThrow(html, CRITICAL_PATTERN, `$1<script type="module" src="${getCriticalJs()}"></script>`, 'detached.html critical script');

    html = replaceOrThrow(html, DETACHED_ENTRY_PATTERN, `$1<script type="module" src="${getDetachedJs()}" data-soai-entry="detached"></script>`, 'detached.html main entry');

    writeFileSync(detachedPath, html, 'utf-8');
    log('Updated detached.html');
};

try {
    log('Updating HTML files with bundled asset references...');
    updateIndexHtml();
    updateDetachedHtml();
    log('HTML files updated successfully!');
} catch (error) {
    console.error('Error updating HTML files:', error);
    process.exit(1);
}
/* SoAI - Update built frontend HTML asset references [frontend/scripts/updateHtmlReferences.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

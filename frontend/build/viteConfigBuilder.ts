/* SoAI - Edition-aware Vite configuration builder [frontend/build/viteConfigBuilder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import path from 'path';
import type { Plugin, UserConfig } from 'vite';

interface FrontendBuildDescriptor {
    readonly edition: 'soai-core' | 'soai-os';
    readonly root: string;
    readonly outputDirectory: string;
    readonly entries: Readonly<Record<string, string>>;
    readonly aliases: Readonly<Record<string, string>>;
}

const supportedBrowserTargets = ['chrome107', 'edge107', 'firefox126', 'safari16'];

const sanitizeChunkName = (value: string | null | undefined): string => {
    if (!value) return 'chunk';
    return (
        value
            .replace(/[^a-zA-Z0-9]+/g, '-')
            .replace(/-+/g, '-')
            .replace(/^-|-$/g, '') || 'chunk'
    );
};

const assetFileName = (name?: string): string => {
    const resolvedName = name || 'asset';
    const extension = path.extname(resolvedName);
    const base = path.basename(resolvedName, extension);
    return extension === '.css' ? `css/${base}-[hash]${extension}` : `assets/${base}-[hash]${extension}`;
};

const jsFileName = (name?: string): string => `js/${sanitizeChunkName(name)}-[hash].js`;

const normalizeModuleId = (moduleId: string, workspaceRoot: string): string => {
    const sourceId = moduleId.split('?')[0] ?? moduleId;
    const isVirtual = sourceId.startsWith('\0');
    const unprefixedId = isVirtual ? sourceId.slice(1) : sourceId;
    if (!path.isAbsolute(unprefixedId)) {
        return isVirtual ? `virtual:${unprefixedId}` : unprefixedId.replaceAll('\\', '/');
    }
    const relativeId = path.relative(workspaceRoot, unprefixedId).replaceAll('\\', '/');
    if (relativeId === '..' || relativeId.startsWith('../')) {
        throw new Error(`Frontend build input is outside the staged workspace: ${path.basename(unprefixedId)}`);
    }
    return isVirtual ? `virtual:${relativeId}` : relativeId;
};

const buildInputManifestPlugin = (descriptor: FrontendBuildDescriptor): Plugin => ({
    name: 'soai-build-input-manifest-v1',
    generateBundle(_outputOptions, bundle): void {
        const workspaceRoot = path.resolve(descriptor.root, descriptor.edition === 'soai-os' ? '../..' : '..');
        const moduleIds = new Set<string>();
        for (const output of Object.values(bundle)) {
            if (output.type !== 'chunk') continue;
            for (const moduleId of Object.keys(output.modules)) {
                moduleIds.add(normalizeModuleId(moduleId, workspaceRoot));
            }
        }
        const sortedModuleIds = [...moduleIds].sort();
        const privateModuleIds = sortedModuleIds.filter((moduleId) => moduleId.startsWith('soai_os/') || moduleId.startsWith('virtual:soai_os/'));
        if (descriptor.edition === 'soai-core' && privateModuleIds.length > 0) {
            throw new Error(`Core frontend contains private modules: ${privateModuleIds.join(', ')}`);
        }
        if (descriptor.edition === 'soai-os' && privateModuleIds.length === 0) {
            throw new Error('SoAI OS frontend contains no private modules');
        }
        const source = `${JSON.stringify({ schema_version: 1, edition: descriptor.edition, module_ids: sortedModuleIds }, null, 2)}\n`;
        this.emitFile({ type: 'asset', fileName: 'build-input-manifest-v1.json', source });
    }
});

const buildViteConfig = (descriptor: FrontendBuildDescriptor, mode: string): UserConfig => {
    const isProduction = mode === 'production';
    return {
        root: descriptor.root,
        logLevel: isProduction ? 'warn' : 'info',
        resolve: { alias: descriptor.aliases },
        base: './',
        publicDir: false,
        plugins: [buildInputManifestPlugin(descriptor)],
        build: {
            target: supportedBrowserTargets,
            manifest: 'manifest.json',
            outDir: descriptor.outputDirectory,
            assetsDir: '.',
            sourcemap: !isProduction,
            minify: isProduction,
            emptyOutDir: true,
            cssCodeSplit: isProduction,
            reportCompressedSize: !isProduction,
            chunkSizeWarningLimit: 50000,
            rollupOptions: {
                input: descriptor.entries,
                output: {
                    entryFileNames: (chunkInfo) => jsFileName(chunkInfo.name),
                    chunkFileNames: (chunkInfo) => jsFileName(chunkInfo.name),
                    assetFileNames: ({ name }) => assetFileName(name),
                    preserveModules: false
                },
                preserveEntrySignatures: 'strict'
            }
        },
        esbuild: { target: supportedBrowserTargets },
        worker: { format: 'es' },
        optimizeDeps: { exclude: ['@xterm/xterm'] }
    };
};

export { buildViteConfig };
export type { FrontendBuildDescriptor };

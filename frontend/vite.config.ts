/* SoAI - Core frontend Vite configuration [frontend/vite.config.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import path from 'path';
import { defineConfig } from 'vite';
import { buildViteConfig, type FrontendBuildDescriptor } from './build/viteConfigBuilder.ts';

const descriptor: FrontendBuildDescriptor = {
    edition: 'soai-core',
    root: import.meta.dirname,
    outputDirectory: 'assets/build',
    entries: {
        critical: path.resolve(import.meta.dirname, 'entries/critical.ts'),
        main: path.resolve(import.meta.dirname, 'entries/main.ts'),
        detached: path.resolve(import.meta.dirname, 'entries/detached.ts')
    },
    aliases: {
        '@app': path.resolve(import.meta.dirname, 'assets/ts/app'),
        '@core': path.resolve(import.meta.dirname, 'assets/ts/core'),
        '@features': path.resolve(import.meta.dirname, 'assets/ts/features'),
        '@pages': path.resolve(import.meta.dirname, 'assets/ts/pages')
    }
};

export default defineConfig(({ mode }) => buildViteConfig(descriptor, mode));

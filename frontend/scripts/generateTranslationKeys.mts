/* SoAI - Frontend translation-key declaration generator [frontend/scripts/generateTranslationKeys.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import fs from 'node:fs/promises';
import path from 'node:path';
import { format, resolveConfig } from 'prettier';
import { detectPluralBaseKeys, flattenLeafStringKeys, formatUnionType, isObject, normalizeTranslations, type JsonValue } from './translationKeyCatalog.mts';
import { buildGeneratedTranslationHeader, resolveGeneratedTranslationLicense } from './translationGeneratedLicense.mts';

const MAX_KEYS_PER_GROUP = 240;
const MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR = 60;

const formatTypeUnion = (typeName: string, members: string[]): string => {
    if (!members.length) {
        return `export type ${typeName} = never;\n`;
    }
    return `export type ${typeName} = ${members.join(' | ')};\n`;
};

const toPascalCase = (value: string): string => {
    const parts = value.split(/[^a-zA-Z0-9]+/).filter((part) => part);
    if (!parts.length) {
        return 'Group';
    }
    return parts.map((part) => part.slice(0, 1).toUpperCase() + part.slice(1)).join('');
};

const toGeneratedFileSegment = (value: string): string => {
    if (value.toLowerCase().startsWith('new')) {
        return `item${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;
    }
    return value;
};

const toGeneratedGroupFileName = (groupSegments: string[]): string => {
    if (groupSegments.length === 0) {
        return 'root.generated.ts';
    }
    return `${groupSegments.map((segment) => toGeneratedFileSegment(segment)).join('__')}.generated.ts`;
};

const buildNamespaceGroups = (namespace: string, keys: string[]): Array<{ groupSegments: string[]; keys: string[] }> => {
    const groups: Array<{ groupSegments: string[]; keys: string[] }> = [];

    const initialBuckets = new Map<string, string[]>();
    for (const key of keys) {
        const parts = key.split('.');
        const ns = parts[0];
        if (ns !== namespace) {
            continue;
        }
        const segment = parts[1] ?? '__root__';
        const existing = initialBuckets.get(segment);
        if (existing) {
            existing.push(key);
        } else {
            initialBuckets.set(segment, [key]);
        }
    }

    const pending: Array<{ groupSegments: string[]; keys: string[] }> = Array.from(initialBuckets.entries()).map(([segment, bucket]) => ({
        groupSegments: [segment],
        keys: bucket
    }));

    while (pending.length > 0) {
        const current = pending.pop();
        if (!current) {
            continue;
        }
        if (current.keys.length <= MAX_KEYS_PER_GROUP) {
            groups.push(current);
            continue;
        }

        const splitDepth = current.groupSegments.length + 1;
        const buckets = new Map<string, string[]>();

        for (const key of current.keys) {
            const parts = key.split('.');
            const segment = parts[splitDepth] ?? '__root__';
            const existing = buckets.get(segment);
            if (existing) {
                existing.push(key);
            } else {
                buckets.set(segment, [key]);
            }
        }

        if (buckets.size === 1 && buckets.has('__root__')) {
            throw new Error(`Unable to split translation key group for namespace ${namespace} at depth ${splitDepth}; key segments exhausted but group still has ${current.keys.length} keys.`);
        }

        for (const [segment, bucket] of buckets.entries()) {
            pending.push({ groupSegments: [...current.groupSegments, segment], keys: bucket });
        }
    }

    const normalized = groups
        .map((group) => ({
            groupSegments: group.groupSegments.filter((segment) => segment && segment !== '__root__'),
            keys: group.keys.sort((a, b) => a.localeCompare(b))
        }))
        .sort((a, b) => a.groupSegments.join('.').localeCompare(b.groupSegments.join('.')));

    if (normalized.length === 0) {
        return [{ groupSegments: [], keys: [] }];
    }

    return normalized;
};

const generate = async (): Promise<void> => {
    const repoRoot = path.resolve(import.meta.dirname, '..');
    const soaiRoot = path.resolve(repoRoot, '..');
    const enJsonPath = path.join(repoRoot, 'assets', 'lang', 'en.json');
    const configuredOutputRoot = process.env['SOAI_TRANSLATION_OUTPUT_ROOT'];
    const privateOutput = Boolean(configuredOutputRoot);
    const outputRoot = configuredOutputRoot ? path.resolve(repoRoot, configuredOutputRoot) : path.join(repoRoot, 'assets', 'ts', 'core', 'i18n');
    const generatedImportRoot = process.env['SOAI_TRANSLATION_IMPORT_ROOT'] ?? '@core/i18n/translationkeys';
    const relativeOutputRoot = path.relative(soaiRoot, outputRoot);
    const privateOutputRoot = path.join(soaiRoot, 'soai_os', 'frontend', 'assets', 'ts', 'i18n');
    if (privateOutput && outputRoot !== privateOutputRoot) {
        throw new Error(`Private translation declarations must remain under soai_os/frontend/assets/ts/i18n: ${relativeOutputRoot}`);
    }
    if (privateOutput && !process.env['SOAI_TRANSLATION_IMPORT_ROOT']) {
        throw new Error('Private translation declarations require SOAI_TRANSLATION_IMPORT_ROOT');
    }
    const generatedLicense = await resolveGeneratedTranslationLicense(soaiRoot, privateOutput);
    const rootOutputPath = path.join(outputRoot, 'translationKeys.generated.ts');
    const groupsRootDir = path.join(outputRoot, 'translationkeys');
    const stagingRootDir = path.join(soaiRoot, '.tmp', 'frontend', 'translationkeys');
    const tmpSuffix = `.__tmp_${process.pid}_${Date.now()}`;
    const tmpGroupsRootDir = `${stagingRootDir}${tmpSuffix}`;
    const tmpRootOutputPath = path.join(stagingRootDir, `translationkeys.generated${tmpSuffix}.ts`);
    const backupSuffix = `.__old_${process.pid}_${Date.now()}`;
    const backupGroupsRootDir = `${stagingRootDir}${backupSuffix}`;
    const backupRootOutputPath = path.join(stagingRootDir, `translationkeys.generated${backupSuffix}.ts`);
    const generatedOutputPath = (stagedPath: string): string => {
        return path.join(groupsRootDir, path.relative(tmpGroupsRootDir, stagedPath));
    };

    const pathExists = async (absPath: string): Promise<boolean> => {
        try {
            await fs.access(absPath);
            return true;
        } catch {
            return false;
        }
    };

    const raw = await fs.readFile(enJsonPath, 'utf8');
    const parsed: JsonValue = JSON.parse(raw);
    if (!isObject(parsed)) {
        throw new Error('frontend/assets/lang/en.json must be a JSON object');
    }
    const translationsValue = parsed['translations'];
    if (!translationsValue || !isObject(translationsValue)) {
        throw new Error('frontend/assets/lang/en.json must include a top-level "translations" object');
    }

    const normalized = normalizeTranslations(translationsValue);
    const keys = new Set<string>();
    if (!privateOutput) {
        flattenLeafStringKeys(normalized, '', keys);
    }
    const catalogPaths = (process.env['SOAI_TRANSLATION_CATALOG_PATHS'] ?? '')
        .split(',')
        .map((catalogPath) => catalogPath.trim())
        .filter(Boolean);
    for (const catalogPath of catalogPaths) {
        const resolvedCatalogPath = path.resolve(repoRoot, catalogPath, 'en.json');
        const relativeCatalogPath = path.relative(soaiRoot, resolvedCatalogPath);
        if (relativeCatalogPath === '..' || relativeCatalogPath.startsWith(`..${path.sep}`)) {
            throw new Error(`Translation catalog escapes the SoAI workspace: ${catalogPath}`);
        }
        const catalogRaw = await fs.readFile(resolvedCatalogPath, 'utf8');
        const catalogParsed: JsonValue = JSON.parse(catalogRaw);
        if (!isObject(catalogParsed)) {
            throw new Error(`Translation catalog must be an object: ${catalogPath}`);
        }
        const catalogTranslations = catalogParsed['translations'];
        if (!catalogTranslations || !isObject(catalogTranslations)) {
            throw new Error(`Translation catalog must include translations: ${catalogPath}`);
        }
        flattenLeafStringKeys(normalizeTranslations(catalogTranslations), '', keys);
    }

    const sortedKeys = Array.from(keys).sort((a, b) => a.localeCompare(b));
    const pluralBaseKeys = detectPluralBaseKeys(keys);

    const prettierConfig = (await resolveConfig(path.join(repoRoot, 'package.json'))) ?? {};
    const formatTs = async (source: string, absPath: string): Promise<string> => {
        return format(source, { ...prettierConfig, filepath: absPath });
    };

    const byNamespace = new Map<string, string[]>();
    for (const key of sortedKeys) {
        const namespace = key.split('.', 1)[0];
        const existing = byNamespace.get(namespace);
        if (existing) {
            existing.push(key);
        } else {
            byNamespace.set(namespace, [key]);
        }
    }

    await fs.mkdir(path.dirname(rootOutputPath), { recursive: true });
    await fs.mkdir(stagingRootDir, { recursive: true });
    await fs.rm(tmpGroupsRootDir, { recursive: true, force: true });
    await fs.rm(tmpRootOutputPath, { force: true });
    await fs.rm(backupGroupsRootDir, { recursive: true, force: true });
    await fs.rm(backupRootOutputPath, { force: true });
    await fs.mkdir(tmpGroupsRootDir, { recursive: true });

    const namespaceTypeNames: Array<{ namespace: string; typeName: string }> = [];

    for (const [namespace, namespaceKeys] of Array.from(byNamespace.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {
        const namespaceDirName = namespace.toLowerCase();
        const namespaceDir = path.join(tmpGroupsRootDir, namespaceDirName);
        await fs.mkdir(namespaceDir, { recursive: true });

        const namespaceGroups = buildNamespaceGroups(namespace, namespaceKeys);
        const namespaceToken = toPascalCase(namespace);
        const namespaceTypeName = `${namespaceToken}TranslationKey`;
        namespaceTypeNames.push({ namespace, typeName: namespaceTypeName });

        const groupTypeNames: string[] = [];

        for (const group of namespaceGroups) {
            const groupToken = group.groupSegments.length > 0 ? group.groupSegments.map((segment) => toPascalCase(segment)).join('') : 'Root';
            const groupTypeName = `${namespaceToken}${groupToken}TranslationKey`;
            groupTypeNames.push(groupTypeName);

            const fileName = toGeneratedGroupFileName(group.groupSegments);
            const filePath = path.join(namespaceDir, fileName);

            const keyGroupIdentity = [namespace, ...group.groupSegments].join('.');
            const banner = buildGeneratedTranslationHeader(path.relative(soaiRoot, generatedOutputPath(filePath)), generatedLicense, privateOutput, `Translation declarations for key group \`${keyGroupIdentity}\``);
            const body = formatUnionType(groupTypeName, group.keys);
            const formatted = await formatTs(`${banner}\n\n${body}`, filePath);
            await fs.writeFile(filePath, formatted, 'utf8');
        }

        const namespaceAggregatorFileName = `${namespace}.generated.ts`;
        const namespaceAggregatorPath = path.join(tmpGroupsRootDir, namespaceAggregatorFileName);
        const groupFileNames = namespaceGroups.map((group) => toGeneratedGroupFileName(group.groupSegments));
        const sectionTypeNames: string[] = [];

        for (let startIndex = 0; startIndex < groupTypeNames.length; startIndex += MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR) {
            const chunkIndex = Math.floor(startIndex / MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR) + 1;
            const chunkTypeNames = groupTypeNames.slice(startIndex, startIndex + MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR);
            const chunkFileNames = groupFileNames.slice(startIndex, startIndex + MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR);
            if (chunkTypeNames.length === 0) {
                continue;
            }
            if (groupTypeNames.length <= MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR) {
                sectionTypeNames.push(...chunkTypeNames);
                break;
            }

            const sectionTypeName = `${namespaceToken}Section${String(chunkIndex).padStart(2, '0')}TranslationKey`;
            const sectionFileName = `${namespace}__section${String(chunkIndex).padStart(2, '0')}.generated.ts`;
            const sectionFilePath = path.join(tmpGroupsRootDir, sectionFileName);
            const sectionImportLines: string[] = [];

            for (let index = 0; index < chunkTypeNames.length; index += 1) {
                sectionImportLines.push(`import type { ${chunkTypeNames[index]} } from '${generatedImportRoot}/${namespaceDirName}/${chunkFileNames[index]}';`);
            }

            const sectionLabel = String(chunkIndex).padStart(2, '0');
            const sectionBanner = buildGeneratedTranslationHeader(path.relative(soaiRoot, generatedOutputPath(sectionFilePath)), generatedLicense, privateOutput, `Translation declarations for \`${namespace}\` namespace section ${sectionLabel}`);
            const sectionUnion = formatTypeUnion(sectionTypeName, chunkTypeNames);
            const sectionFormatted = await formatTs(`${sectionBanner}\n${sectionImportLines.length ? `\n${sectionImportLines.join('\n')}\n` : '\n'}\n${sectionUnion}`, sectionFilePath);
            await fs.writeFile(sectionFilePath, sectionFormatted, 'utf8');
            sectionTypeNames.push(sectionTypeName);
        }

        const importLines: string[] = [];

        if (groupTypeNames.length <= MAX_GROUP_TYPES_PER_NAMESPACE_AGGREGATOR) {
            for (let index = 0; index < groupTypeNames.length; index += 1) {
                importLines.push(`import type { ${groupTypeNames[index]} } from '${generatedImportRoot}/${namespaceDirName}/${groupFileNames[index]}';`);
            }
        } else {
            for (let index = 0; index < sectionTypeNames.length; index += 1) {
                const sectionFileName = `${namespace}__section${String(index + 1).padStart(2, '0')}.generated.ts`;
                importLines.push(`import type { ${sectionTypeNames[index]} } from '${generatedImportRoot}/${sectionFileName}';`);
            }
        }

        const banner = buildGeneratedTranslationHeader(path.relative(soaiRoot, generatedOutputPath(namespaceAggregatorPath)), generatedLicense, privateOutput, `Translation declarations for the \`${namespace}\` namespace`);
        const union = formatTypeUnion(namespaceTypeName, sectionTypeNames);
        const formatted = await formatTs(`${banner}\n${importLines.length ? `\n${importLines.join('\n')}\n` : '\n'}\n${union}`, namespaceAggregatorPath);
        await fs.writeFile(namespaceAggregatorPath, formatted, 'utf8');
    }

    const rootImports = namespaceTypeNames.map(({ namespace, typeName }) => `import type { ${typeName} } from '${generatedImportRoot}/${namespace}.generated.ts';`);
    const rootUnion = formatTypeUnion(
        'TranslationKey',
        namespaceTypeNames.map((entry) => entry.typeName)
    );
    const rootPlural = formatUnionType('PluralBaseKey', pluralBaseKeys);
    const rootBanner = buildGeneratedTranslationHeader(path.relative(soaiRoot, rootOutputPath), generatedLicense, privateOutput, 'Translation root declaration catalog');
    const baseContractTypes = privateOutput ? '' : '\nexport type BaseTranslationKey = TranslationKey;\nexport type BasePluralBaseKey = PluralBaseKey;\n';

    const rootFormatted = await formatTs(`${rootBanner}\n\n${rootImports.join('\n')}\n\n${rootUnion}\n${rootPlural}${baseContractTypes}`, tmpRootOutputPath);
    await fs.writeFile(tmpRootOutputPath, rootFormatted, 'utf8');

    if (await pathExists(groupsRootDir)) {
        await fs.rename(groupsRootDir, backupGroupsRootDir);
    }

    await fs.rename(tmpGroupsRootDir, groupsRootDir);
    await fs.rm(backupGroupsRootDir, { recursive: true, force: true });

    if (await pathExists(rootOutputPath)) {
        await fs.rename(rootOutputPath, backupRootOutputPath);
    }

    await fs.rename(tmpRootOutputPath, rootOutputPath);
    await fs.rm(backupRootOutputPath, { force: true });
};

await generate();

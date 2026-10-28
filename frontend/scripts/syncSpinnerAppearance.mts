/* SoAI - Synchronizes authored comet spinner geometry [frontend/scripts/syncSpinnerAppearance.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import type { AtRule, Rule } from 'postcss';

const { values } = parseArgs({ options: { target: { type: 'string', default: 'frontend' }, check: { type: 'boolean', default: false } } });
if (values.target !== 'frontend' && values.target !== 'website') {
    throw new Error('Spinner appearance target must be frontend or website.');
}
const postcss: typeof import('postcss') = createRequire(new URL(values.target === 'website' ? '../../soai.to/package.json' : '../package.json', import.meta.url))('postcss');
const sourcePath = fileURLToPath(new URL('../assets/css/components/feedback/spinner.css', import.meta.url));
const targetPath = fileURLToPath(new URL(values.target === 'frontend' ? '../assets/css/boot.css' : '../../soai.to/public/assets/css/base.css', import.meta.url));
const source = postcss.parse(await readFile(sourcePath, 'utf8'), { from: sourcePath });
const targetText = await readFile(targetPath, 'utf8');
const target = postcss.parse(targetText, { from: targetPath });
const normalizeCssValue = (text: string): string =>
    text
        .replace(/\s+/gu, ' ')
        .replace(/\s*([(),])\s*/gu, '$1')
        .trim();
const appearanceProperties = new Set(['background-image', 'mask', 'border-radius']);
let trail = '';
source.walkDecls('--soai-spinner-trail', (declaration) => {
    trail = declaration.value;
});
if (!trail) throw new Error('Canonical spinner trail is required.');
const appearance = new Map<string, string>();
source.walkRules((rule) => {
    if (!rule.selectors.includes(':where(.loading-spinner)')) return;
    rule.walkDecls((declaration) => {
        if (!appearanceProperties.has(declaration.prop)) return;
        if (appearance.has(declaration.prop)) throw new Error(`Duplicate spinner appearance declaration: ${declaration.prop}`);
        appearance.set(declaration.prop, declaration.prop === 'background-image' ? 'none' : declaration.value);
    });
});
if (appearance.size !== appearanceProperties.size) throw new Error('Canonical spinner appearance is incomplete.');
const selector = values.target === 'frontend' ? '.page-preloader-spinner' : '.loading-spinner';
let changed = false;
const targetAppearanceRules: Rule[] = [];
target.walkRules((rule) => {
    if (rule.selector !== selector || (values.target === 'frontend' ? rule.parent?.type !== 'atrule' || rule.parent.name !== 'layer' : rule.parent?.type !== 'root')) return;
    targetAppearanceRules.push(rule);
    const matchedProperties = new Set<string>();
    rule.walkDecls((declaration) => {
        const value = appearance.get(declaration.prop);
        if (value === undefined) return;
        if (matchedProperties.has(declaration.prop)) throw new Error(`Duplicate target spinner declaration: ${declaration.prop}`);
        matchedProperties.add(declaration.prop);
        if (normalizeCssValue(declaration.value) !== normalizeCssValue(value)) {
            declaration.value = value;
            changed = true;
        }
    });
    if (matchedProperties.size !== appearanceProperties.size) throw new Error('Target spinner appearance is incomplete.');
});
{
    const rule = targetAppearanceRules[0];
    if (rule === undefined) throw new Error('Target spinner is required.');
    const expected = new Map([
        ['--soai-spinner-angle', '0deg'],
        ['--soai-spinner-trail', trail],
        ['--soai-spinner-duration', values.target === 'frontend' ? 'var(--spinner-duration-1000)' : '1000ms'],
        ['--soai-spinner-easing', values.target === 'frontend' ? 'var(--ease-linear)' : 'linear'],
        ['--motion-essential-duration', '0ms'],
        ['position', 'relative'],
        ['overflow', 'clip'],
        ['animation', values.target === 'frontend' ? 'preloader-spinner-fade-in var(--duration-1000) var(--ease-out) both' : 'none']
    ]);
    for (const [property, value] of expected) {
        const existing = rule.nodes.find((node) => node.type === 'decl' && node.prop === property);
        if (existing?.type === 'decl') {
            if (normalizeCssValue(existing.value) === normalizeCssValue(value)) continue;
            existing.value = value;
        } else {
            rule.append({ prop: property, value });
        }
        changed = true;
    }
    const trailRules: Rule[] = [];
    source.walkRules((rule) => {
        if (rule.selectors.includes(':where(.loading-spinner)::before')) trailRules.push(rule);
    });
    const authored = trailRules[0]?.clone({ selector: `${selector}::before` });
    if (authored === undefined || trailRules.length !== 1) throw new Error('Canonical spinner trail layer is required.');
    const existingRules: Rule[] = [];
    target.walkRules(`${selector}::before`, (rule) => {
        if (rule.parent === targetAppearanceRules[0]?.parent) existingRules.push(rule);
    });
    if (existingRules.length > 1) throw new Error('Duplicate spinner trail layer.');
    const existing = existingRules[0];
    if (existing === undefined) {
        rule.after(authored);
        changed = true;
    } else if (normalizeCssValue(existing.toString()) !== normalizeCssValue(authored.toString())) {
        existing.replaceWith(authored);
        changed = true;
    }
}
if (targetAppearanceRules.length !== 1) throw new Error(`Expected one authored spinner rule, received ${targetAppearanceRules.length}.`);
const targetAppearanceRule = targetAppearanceRules[0];
if (targetAppearanceRule === undefined) throw new Error('Target spinner rule is required.');
const motionDeclarations = [
    { name: 'property', parameters: '--soai-spinner-angle' },
    { name: 'keyframes', parameters: 'spin' },
    { name: 'keyframes', parameters: 'spinner-trail-rotate' }
];
for (const { name, parameters } of motionDeclarations) {
    const sourceRules: AtRule[] = [];
    const targetRules: AtRule[] = [];
    source.walkAtRules(name, (rule) => {
        if (rule.params === parameters) sourceRules.push(rule);
    });
    target.walkAtRules(name, (rule) => {
        if (rule.params === parameters) targetRules.push(rule);
    });
    const authored = sourceRules[0];
    if (sourceRules.length !== 1 || authored === undefined || targetRules.length > 1) throw new Error(`Invalid spinner motion declaration: ${parameters}`);
    const existing = targetRules[0];
    if (existing === undefined) {
        targetAppearanceRule.before(authored.clone());
        changed = true;
    } else {
        const precedesImport = target.nodes.some((node) => node.type === 'atrule' && node.name === 'import' && target.nodes.indexOf(node) > target.nodes.indexOf(existing));
        if (existing.parent === target && precedesImport) {
            existing.remove();
            targetAppearanceRule.before(authored.clone());
            changed = true;
        } else if (normalizeCssValue(existing.toString()) !== normalizeCssValue(authored.toString())) {
            existing.replaceWith(authored.clone());
            changed = true;
        }
    }
}
const densityRules: AtRule[] = [];
const existingDensityRules: AtRule[] = [];
source.walkAtRules('media', (rule) => {
    if (rule.params === '(resolution < 1dppx)') densityRules.push(rule);
});
target.walkAtRules('media', (rule) => {
    if (rule.params === '(resolution < 1dppx)') existingDensityRules.push(rule);
});
const density = densityRules[0]?.clone();
if (!density || densityRules.length !== 1 || existingDensityRules.length > 1) throw new Error('Invalid spinner density rules.');
density.walkRules((rule) => {
    const isTrail = rule.selector.endsWith('::before');
    rule.selector = isTrail ? `${selector}::before` : selector;
    if (!isTrail && values.target === 'frontend') {
        rule.walkDecls('animation', (declaration) => {
            declaration.value += ', preloader-spinner-fade-in var(--duration-1000) var(--ease-out) both';
        });
        rule.walkDecls('--motion-essential-duration', (declaration) => {
            declaration.value = 'var(--spinner-duration-1000), 0ms';
        });
    }
});
const existingDensity = existingDensityRules[0];
if (!existingDensity) {
    const trailRule = targetAppearanceRule.parent?.nodes.find((node) => node.type === 'rule' && node.selector === `${selector}::before`);
    if (!trailRule) throw new Error('Target spinner trail layer is required.');
    trailRule.after(density);
    changed = true;
} else if (normalizeCssValue(existingDensity.toString()) !== normalizeCssValue(density.toString())) {
    existingDensity.replaceWith(density);
    changed = true;
}
if (changed && values.check) throw new Error(`Spinner appearance is stale: ${targetPath}`);
if (changed) await writeFile(targetPath, target.toString());

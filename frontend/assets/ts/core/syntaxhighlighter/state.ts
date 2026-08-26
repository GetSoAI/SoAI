/* SoAI - Shared frontend syntax highlighter state [frontend/assets/ts/core/syntaxhighlighter/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { PRIMARY_LANGUAGE_DEFINITIONS } from '@core/syntaxhighlighter/constants.ts';
import { SECONDARY_LANGUAGE_DEFINITIONS } from '@core/syntaxhighlighter/mappers.ts';
import type { LanguageDefinition } from '@core/syntaxhighlighter/types.ts';

const LANGUAGE_DEFINITIONS: LanguageDefinition[] = [...PRIMARY_LANGUAGE_DEFINITIONS, ...SECONDARY_LANGUAGE_DEFINITIONS];

const LANGUAGE_BY_ID: Map<string, LanguageDefinition> = new Map();
const LANGUAGE_BY_ALIAS: Map<string, string> = new Map();

LANGUAGE_DEFINITIONS.forEach((definition) => {
    LANGUAGE_BY_ID.set(definition.id, definition);
    const aliases = isArray(definition.aliases) ? definition.aliases : [];
    aliases.forEach((alias) => {
        LANGUAGE_BY_ALIAS.set(String(alias).toLowerCase(), definition.id);
    });
});

export { LANGUAGE_BY_ALIAS, LANGUAGE_BY_ID, LANGUAGE_DEFINITIONS };

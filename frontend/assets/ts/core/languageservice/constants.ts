/* SoAI - Shared language service constants [frontend/assets/ts/core/languageservice/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createModuleLogger, type ModuleLogger } from '@core/moduleContext.ts';

const LANGUAGES_PATH = 'lang';
const PRIMARY_LANGUAGE = 'en';
const MANIFEST_FILE = 'manifest.json';
const FLAGS_FILE = 'languageFlags.json';
const SERVICE_NAME = 'LanguageService';
const EVENT_CHANGE = 'soai:language:changed';
const EVENT_REQUEST = 'soai:language:change-requested';
const KEY_SPLIT_RE = /[.:]/;
const log: ModuleLogger = createModuleLogger(SERVICE_NAME, { defaultLevel: 'warn' });

export { EVENT_CHANGE, EVENT_REQUEST, FLAGS_FILE, KEY_SPLIT_RE, LANGUAGES_PATH, MANIFEST_FILE, PRIMARY_LANGUAGE, SERVICE_NAME, log };

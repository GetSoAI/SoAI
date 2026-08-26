/* SoAI - Frontend main entry [frontend/entries/main.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import './basePath.ts';
import './styles/main.css';
import { startSoaiEntry } from './shared.ts';
import { CORE_FRONTEND_EDITION } from '../assets/ts/app/edition/coreFrontendEdition.ts';

void startSoaiEntry('main', CORE_FRONTEND_EDITION);

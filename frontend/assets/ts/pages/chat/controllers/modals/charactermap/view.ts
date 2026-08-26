/* SoAI - Character map modal view transitions [frontend/assets/ts/pages/chat/controllers/modals/charactermap/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setControlDisabledState, setControlDisabledStateForEach } from '@core/ui/controls/disabledState.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHARACTER_MAP_DEFAULT_FONT_ID, CHARACTER_MAP_FONT_CLASSES, getCharacterMapFont, type CharacterMapCatalogIndex, type CharacterMapResultItem } from '@features/chat/public.ts';
import type { CharacterMapModalRefs } from '@pages/chat/controllers/modals/charactermap/types.ts';

const setVisible = (element: HTMLElement, visible: boolean): void => {
    element.classList.toggle('u-hidden', !visible);
};

const resetCharacterMapView = (refs: CharacterMapModalRefs): void => {
    refs.search.value = '';
    refs.staging.value = '';
    refs.grid.replaceChildren();
    refs.grid.scrollTop = 0;
    refs.grid.setAttribute('aria-busy', 'false');
    refs.grid.classList.remove(...CHARACTER_MAP_FONT_CLASSES);
    refs.grid.classList.add(getCharacterMapFont(CHARACTER_MAP_DEFAULT_FONT_ID).className);
    refs.font.value = CHARACTER_MAP_DEFAULT_FONT_ID;
    refs.subset.replaceChildren();
    refs.codePoints.textContent = '';
    refs.name.textContent = '';
    clearStatusSurface(refs.status);
    setVisible(refs.loading, true);
    setVisible(refs.error, false);
    setVisible(refs.empty, false);
    setVisible(refs.grid, false);
    setControlDisabledStateForEach([refs.searchButton, refs.font, refs.subset, refs.retry, refs.select, refs.copy, refs.insert], true);
};

const populateCharacterMapSelectors = (refs: CharacterMapModalRefs, index: CharacterMapCatalogIndex): void => {
    const documentValue = refs.subset.ownerDocument;
    const options = documentValue.createDocumentFragment();
    for (const selector of index.selectors) {
        const option = documentValue.createElement('option');
        option.value = selector.id;
        option.textContent = selector.id === 'unicode:all' ? i18n.t('chat.characterMap.allUnicode') : selector.id === 'emoji:all' ? i18n.t('chat.characterMap.allEmoji') : selector.label;
        options.append(option);
    }
    refs.subset.replaceChildren(options);
    refs.subset.value = index.defaultSelectorId;
};

const showCharacterMapReady = (refs: CharacterMapModalRefs): void => {
    setVisible(refs.loading, false);
    setVisible(refs.error, false);
    setControlDisabledStateForEach([refs.searchButton, refs.font, refs.subset], false);
};

const showCharacterMapLoading = (refs: CharacterMapModalRefs): void => {
    setVisible(refs.loading, true);
    setVisible(refs.error, false);
    setVisible(refs.empty, false);
    setVisible(refs.grid, false);
    setControlDisabledStateForEach([refs.searchButton, refs.font, refs.subset, refs.retry, refs.select], true);
};

const showCharacterMapLoadFailure = (refs: CharacterMapModalRefs): void => {
    setVisible(refs.loading, false);
    setVisible(refs.error, true);
    setVisible(refs.grid, false);
    setVisible(refs.empty, false);
    setControlDisabledStateForEach([refs.searchButton, refs.font, refs.subset, refs.select], true);
    setControlDisabledState(refs.retry, false);
};

const projectCharacterMapActive = (refs: CharacterMapModalRefs, active: CharacterMapResultItem | null): void => {
    refs.codePoints.textContent = active?.codePointText ?? '';
    refs.name.textContent = active?.name ?? '';
    setTooltipText(refs.codePoints, active?.codePointText ?? '');
    setTooltipText(refs.name, active?.name ?? '');
    setControlDisabledState(refs.select, active === null);
};

const projectCharacterMapResult = (refs: CharacterMapModalRefs, count: number, active: CharacterMapResultItem | null): void => {
    setVisible(refs.empty, count === 0);
    setVisible(refs.grid, count > 0);
    projectCharacterMapActive(refs, active);
    setStatusSurface({ surface: refs.status, message: i18n.t('chat.characterMap.resultCount', { count }) });
};

const projectStagingActions = (refs: CharacterMapModalRefs, copyPending: boolean): void => {
    const empty = refs.staging.value.length === 0;
    if (!copyPending) setControlDisabledState(refs.copy, empty);
    setControlDisabledState(refs.insert, empty);
};

const showCharacterMapResultFailure = (refs: CharacterMapModalRefs): void => setStatusSurface({ surface: refs.status, message: i18n.t('chat.characterMap.resultsUnavailable'), tone: 'error' });

export { populateCharacterMapSelectors, projectCharacterMapActive, projectCharacterMapResult, projectStagingActions, resetCharacterMapView, showCharacterMapLoadFailure, showCharacterMapLoading, showCharacterMapReady, showCharacterMapResultFailure };

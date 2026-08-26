/* SoAI - File explorer feature actions [frontend/assets/ts/features/fileexplorer/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const FILE_EXPLORER_ACTION_REFRESH = 'fileExplorer.refresh';
export const FILE_EXPLORER_ACTION_NAVIGATE_HOME = 'fileExplorer.navigateHome';
export const FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS = 'fileExplorer.navigatePrevious';
export const FILE_EXPLORER_ACTION_NAVIGATE_NEXT = 'fileExplorer.navigateNext';
export const FILE_EXPLORER_ACTION_NAVIGATE_UP = 'fileExplorer.navigateUp';
export const FILE_EXPLORER_ACTION_NAVIGATE_PATH = 'fileExplorer.navigatePath';
export const FILE_EXPLORER_ACTION_PATH_EDIT_START = 'fileExplorer.pathEditStart';
export const FILE_EXPLORER_ACTION_PATH_EDIT_SAVE = 'fileExplorer.pathEditSave';
export const FILE_EXPLORER_ACTION_ROW_OPEN = 'fileExplorer.rowOpen';
export const FILE_EXPLORER_ACTION_SORT = 'fileExplorer.sort';
export const FILE_EXPLORER_ACTION_METADATA_COPY = 'fileExplorer.metadataCopy';

export const FILE_EXPLORER_ACTION_SELECTION_METADATA = 'fileExplorer.selectionMetadata';
export const FILE_EXPLORER_ACTION_SELECTION_RENAME = 'fileExplorer.selectionRename';
export const FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK = 'fileExplorer.selectionSoaiLink';
export const FILE_EXPLORER_ACTION_SELECTION_DELETE = 'fileExplorer.selectionDelete';
export const FILE_EXPLORER_ACTION_SELECTION_COPY = 'fileExplorer.selectionCopy';
export const FILE_EXPLORER_ACTION_SELECTION_MOVE = 'fileExplorer.selectionMove';
export const FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD = 'fileExplorer.selectionDownload';
export const FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL = 'fileExplorer.selectionSelectAll';
export const FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL = 'fileExplorer.selectionDeselectAll';
export const FILE_EXPLORER_ACTION_SELECTION_INVERSE = 'fileExplorer.selectionInverse';
export const FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE = 'fileExplorer.toggleSelectionMode';
export const FILE_EXPLORER_ACTION_COPY_HERE = 'fileExplorer.copyHere';
export const FILE_EXPLORER_ACTION_MOVE_HERE = 'fileExplorer.moveHere';
export const FILE_EXPLORER_ACTION_MODE_CANCEL = 'fileExplorer.modeCancel';

export const FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE = 'fileExplorer.taskPanelToggle';
export const FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE = 'fileExplorer.toggleViewMode';
export const FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT = 'fileExplorer.clearHighlight';

export const FILE_EXPLORER_ACTION_SELECT_ROW = 'fileExplorer.selectRow';
export const FILE_EXPLORER_ACTION_SELECT_ALL = 'fileExplorer.selectAll';
export const FILE_EXPLORER_ACTION_UPLOAD_FILES = 'fileExplorer.uploadFiles';
export const FILE_EXPLORER_ACTION_NEW_ENTRY = 'fileExplorer.newEntry';

export type FileExplorerClickActionId =
    | typeof FILE_EXPLORER_ACTION_REFRESH
    | typeof FILE_EXPLORER_ACTION_NAVIGATE_HOME
    | typeof FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS
    | typeof FILE_EXPLORER_ACTION_NAVIGATE_NEXT
    | typeof FILE_EXPLORER_ACTION_NAVIGATE_UP
    | typeof FILE_EXPLORER_ACTION_NAVIGATE_PATH
    | typeof FILE_EXPLORER_ACTION_PATH_EDIT_START
    | typeof FILE_EXPLORER_ACTION_PATH_EDIT_SAVE
    | typeof FILE_EXPLORER_ACTION_ROW_OPEN
    | typeof FILE_EXPLORER_ACTION_SORT
    | typeof FILE_EXPLORER_ACTION_METADATA_COPY
    | typeof FILE_EXPLORER_ACTION_SELECTION_METADATA
    | typeof FILE_EXPLORER_ACTION_SELECTION_RENAME
    | typeof FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK
    | typeof FILE_EXPLORER_ACTION_SELECTION_DELETE
    | typeof FILE_EXPLORER_ACTION_SELECTION_COPY
    | typeof FILE_EXPLORER_ACTION_SELECTION_MOVE
    | typeof FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD
    | typeof FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL
    | typeof FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL
    | typeof FILE_EXPLORER_ACTION_SELECTION_INVERSE
    | typeof FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE
    | typeof FILE_EXPLORER_ACTION_COPY_HERE
    | typeof FILE_EXPLORER_ACTION_MOVE_HERE
    | typeof FILE_EXPLORER_ACTION_MODE_CANCEL
    | typeof FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE
    | typeof FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE
    | typeof FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT;

export type FileExplorerChangeActionId = typeof FILE_EXPLORER_ACTION_SELECT_ROW | typeof FILE_EXPLORER_ACTION_SELECT_ALL | typeof FILE_EXPLORER_ACTION_UPLOAD_FILES | typeof FILE_EXPLORER_ACTION_NEW_ENTRY;

export type FileexplorerActionId = FileExplorerClickActionId | FileExplorerChangeActionId;

const { guard: isFileExplorerClickActionId } = createActionIdSet(
    FILE_EXPLORER_ACTION_REFRESH,
    FILE_EXPLORER_ACTION_NAVIGATE_HOME,
    FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS,
    FILE_EXPLORER_ACTION_NAVIGATE_NEXT,
    FILE_EXPLORER_ACTION_NAVIGATE_UP,
    FILE_EXPLORER_ACTION_NAVIGATE_PATH,
    FILE_EXPLORER_ACTION_PATH_EDIT_START,
    FILE_EXPLORER_ACTION_PATH_EDIT_SAVE,
    FILE_EXPLORER_ACTION_ROW_OPEN,
    FILE_EXPLORER_ACTION_SORT,
    FILE_EXPLORER_ACTION_METADATA_COPY,
    FILE_EXPLORER_ACTION_SELECTION_METADATA,
    FILE_EXPLORER_ACTION_SELECTION_RENAME,
    FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK,
    FILE_EXPLORER_ACTION_SELECTION_DELETE,
    FILE_EXPLORER_ACTION_SELECTION_COPY,
    FILE_EXPLORER_ACTION_SELECTION_MOVE,
    FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD,
    FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL,
    FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL,
    FILE_EXPLORER_ACTION_SELECTION_INVERSE,
    FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE,
    FILE_EXPLORER_ACTION_COPY_HERE,
    FILE_EXPLORER_ACTION_MOVE_HERE,
    FILE_EXPLORER_ACTION_MODE_CANCEL,
    FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE,
    FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE,
    FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT
);

const { guard: isFileExplorerChangeActionId } = createActionIdSet(FILE_EXPLORER_ACTION_SELECT_ROW, FILE_EXPLORER_ACTION_SELECT_ALL, FILE_EXPLORER_ACTION_UPLOAD_FILES, FILE_EXPLORER_ACTION_NEW_ENTRY);

export const isFileexplorerActionId = (value: string | undefined): value is FileexplorerActionId => isFileExplorerClickActionId(value) || isFileExplorerChangeActionId(value);

export { isFileExplorerClickActionId, isFileExplorerChangeActionId };

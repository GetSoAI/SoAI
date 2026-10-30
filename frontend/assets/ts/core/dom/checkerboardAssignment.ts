/* SoAI - Shared DOM checkerboard assignment [frontend/assets/ts/core/dom/checkerboardAssignment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type CheckerboardClassName = 'checkerboard-light' | 'checkerboard-dark';

interface CheckerboardClassOptions {
    columns?: number;
    start?: CheckerboardClassName;
}

const CHECKERBOARD_CLASS_PAIR = 'checkerboard-light checkerboard-dark';

const invertCheckerboardClass = (className: CheckerboardClassName): CheckerboardClassName => (className === 'checkerboard-light' ? 'checkerboard-dark' : 'checkerboard-light');

const resolveCheckerboardClass = (index: number, options: CheckerboardClassOptions = {}): CheckerboardClassName => {
    const startClass = options.start ?? 'checkerboard-light';
    const normalizedIndex = Number.isFinite(index) && index > 0 ? Math.trunc(index) : 0;
    const columns = options.columns && Number.isFinite(options.columns) && options.columns > 0 ? Math.trunc(options.columns) : 1;
    const rowIndex = Math.floor(normalizedIndex / columns);
    const columnIndex = normalizedIndex % columns;
    return (rowIndex + columnIndex) % 2 === 0 ? startClass : invertCheckerboardClass(startClass);
};

const CHECKERBOARD_CLASS_NAMES: ReadonlySet<string> = new Set(CHECKERBOARD_CLASS_PAIR.split(' '));

const countCheckerboardMatches = (rows: readonly HTMLElement[], offset: number): number => rows.reduce((count, row, index) => count + (row.classList.contains(resolveCheckerboardClass(index + offset)) ? 1 : 0), 0);

const applyCheckerboardClasses = (items: readonly Element[], assignments: readonly CheckerboardClassName[]): void => {
    const changes = items.flatMap((item, index) => {
        const assigned = assignments[index];
        if (assigned === undefined) throw new Error('Checkerboard assignment missing for item');
        const previous = invertCheckerboardClass(assigned);
        if (item.classList.contains(assigned) && !item.classList.contains(previous)) return [];
        const animations = typeof item.getAnimations === 'function' ? item.getAnimations({ subtree: true }) : [];
        return [{ item, assigned, previous, animations: new Set(animations) }];
    });
    changes.forEach(({ item, assigned, previous }) => {
        item.classList.remove(previous);
        item.classList.add(assigned);
    });
    const updatedAnimations = changes.map(({ item, animations }) => ({
        animations,
        current: typeof item.getAnimations === 'function' ? item.getAnimations({ subtree: true }) : []
    }));
    updatedAnimations.forEach(({ animations, current }) => {
        for (const animation of current) {
            if (!animations.has(animation) && 'transitionProperty' in animation && (animation.transitionProperty === 'background-color' || animation.transitionProperty === 'background-image' || animation.transitionProperty === 'box-shadow')) {
                animation.finish();
            }
        }
    });
};

const syncStableCheckerboardClasses = (rows: readonly HTMLElement[]): void => {
    const offset = countCheckerboardMatches(rows, 1) > countCheckerboardMatches(rows, 0) ? 1 : 0;
    applyCheckerboardClasses(
        rows,
        rows.map((_row, index) => resolveCheckerboardClass(index + offset))
    );
};

export { applyCheckerboardClasses, CHECKERBOARD_CLASS_NAMES, CHECKERBOARD_CLASS_PAIR, invertCheckerboardClass, resolveCheckerboardClass, syncStableCheckerboardClasses };
export type { CheckerboardClassName, CheckerboardClassOptions };

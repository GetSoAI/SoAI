/* SoAI - Model detail page widgets parameter templates public contracts [frontend/assets/ts/pages/modeldetail/widgets/parametertemplates/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonArray, JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type BooleanInputProps = { id: string; key: string; value: string | boolean | null | undefined };

type NumericInputProps = {
    id: string;
    key: string;
    value: string | number | null | undefined;
    minimum?: number | undefined;
    maximum?: number | undefined;
    numericType: 'integer' | 'float';
};

type ChoiceInputProps = {
    id: string;
    key: string;
    value: JsonValue | undefined;
    choices?: JsonValue[];
};

type TextInputProps = {
    id: string;
    key: string;
    value: string | null | undefined;
};

type ArrayItemProps = {
    key: string;
    index: number;
    value: JsonValue;
    itemType?: string | undefined;
    fixedArity: boolean;
};

type ArrayInputProps = {
    id: string;
    key: string;
    value: JsonArray;
    itemType?: string | undefined;
    valueCount?: number | undefined;
};

type ObjectInputProps = {
    id: string;
    key: string;
    value: JsonObject | string | null | undefined;
};

export type { ArrayInputProps, ArrayItemProps, BooleanInputProps, ChoiceInputProps, NumericInputProps, ObjectInputProps, TextInputProps };

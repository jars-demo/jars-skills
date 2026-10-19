# type-safety — references

Key reading for the concepts and patterns in this skill.

## TypeScript

- [TypeScript strict mode flags](https://www.typescriptlang.org/tsconfig#strict) — full list
  of what `strict: true` enables and what each flag catches.
- [TypeScript handbook — Narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html) — official guide to type guards, `in` checks, `instanceof`, discriminated unions.
- [TypeScript handbook — Template literal types & branded types](https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html)
- [Zod documentation](https://zod.dev) — schema-first validation library used throughout this skill.

## Discriminated unions and exhaustiveness

- [TypeScript discriminated unions](https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes-func.html#discriminated-unions)
- `assertNever` exhaustiveness pattern — originally from the TypeScript deep dive by
  Basarat Ali Syed: https://basarat.gitbook.io/typescript/type-system/discriminated-unions

## Python

- [mypy strict mode](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict) — all flags enabled by `--strict`.
- [Pydantic v2 documentation](https://docs.pydantic.dev/latest/) — model validation, field constraints, and custom validators used in this skill.

## Branded types

- [TypeScript branding pattern](https://egghead.io/blog/using-branded-types-in-typescript) — practical guide with smart constructors.

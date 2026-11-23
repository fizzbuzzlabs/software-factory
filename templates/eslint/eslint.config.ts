import js from "@eslint/js";
import vitest from "@vitest/eslint-plugin";
import type { Linter } from "eslint";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const testFiles = ["**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx", "tests/**"];
const loggerFiles = ["src/logger.ts"];

const parseBodiesWithASchema = {
  selector: "CallExpression[callee.property.name='json'][typeArguments]",
  message: "A type argument on .json() asserts the body's type. Parse it with a schema instead.",
};

const handleOrPropagateRejections = {
  selector:
    "CallExpression[callee.property.name='catch'] > :function:matches([body.type='BlockStatement'][body.body.length=0], [body.type='Identifier'][body.name='undefined'], [body.type='Literal'][body.raw='null'], [body.type='UnaryExpression'][body.operator='void'][body.argument.type='Literal'])",
  message: "A .catch() that does nothing swallows the failure. Handle it, log it with context, or let it propagate.",
};

const logThroughTheLogger = {
  selector:
    "CallExpression[callee.property.name='write'][callee.object.object.name='process'][callee.object.property.name=/^(stdout|stderr)$/]",
  message: "Log through the logger module instead of writing to process.stdout or process.stderr.",
};

const mockOnlyWhatYouDontOwn = {
  selector:
    "CallExpression[callee.object.name='vi'][callee.property.name=/^(mock|doMock)$/][arguments.0.value=/^(\\.{1,2}|@|~)\\//]",
  message: "Mock only what you don't own. Reach this module through a real caller's path instead.",
};

const boundaryDiscipline: Linter.RulesRecord = {
  "@typescript-eslint/consistent-type-assertions": ["error", { assertionStyle: "never" }],
  "@typescript-eslint/no-unsafe-argument": "error",
  "@typescript-eslint/no-unsafe-assignment": "error",
  "@typescript-eslint/no-unsafe-call": "error",
  "@typescript-eslint/no-unsafe-member-access": "error",
  "@typescript-eslint/no-unsafe-return": "error",
};

const typeSystemDiscipline: Linter.RulesRecord = {
  "@typescript-eslint/no-explicit-any": "error",
  "@typescript-eslint/no-non-null-assertion": "error",
  "@typescript-eslint/ban-ts-comment": "error",
};

const modelTheDomain: Linter.RulesRecord = {
  "@typescript-eslint/switch-exhaustiveness-check": "error",
};

const neverSwallowAFailure: Linter.RulesRecord = {
  "@typescript-eslint/no-floating-promises": ["error", { ignoreVoid: false }],
  "@typescript-eslint/no-misused-promises": "error",
  "@typescript-eslint/return-await": "error",
  "@typescript-eslint/only-throw-error": "error",
  "@typescript-eslint/prefer-promise-reject-errors": "error",
  "@typescript-eslint/use-unknown-in-catch-callback-variable": "error",
  "no-empty": ["error", { allowEmptyCatch: false }],
};

const fixRootCauses: Linter.RulesRecord = {
  "@typescript-eslint/no-unnecessary-condition": "error",
};

const oneLogger: Linter.RulesRecord = {
  "no-restricted-globals": [
    "error",
    { name: "console", message: "Log through the logger module. Take the logger, not console, as a dependency." },
  ],
};

const minimizeReaderLoad: Linter.RulesRecord = {
  "max-lines": ["error", { max: 500 }],
  "max-lines-per-function": ["error", { max: 100 }],
  "no-restricted-imports": [
    "error",
    {
      paths: [
        { name: "node:async_hooks", message: "Pass values through parameters and return values, not ambient context." },
        { name: "async_hooks", message: "Pass values through parameters and return values, not ambient context." },
      ],
    },
  ],
};

const subtractBeforeYouAdd: Linter.RulesRecord = {
  "@typescript-eslint/no-unused-vars": "error",
  "no-unused-private-class-members": "error",
};

const testBehaviorNotImplementation: Linter.RulesRecord = {
  "vitest/expect-expect": "error",
  "vitest/valid-expect": "error",
};

const assertionsAllowedInTests: Linter.RulesRecord = {
  "@typescript-eslint/consistent-type-assertions": "off",
  "@typescript-eslint/no-non-null-assertion": "off",
};

const lengthCapsOnlyInProduction: Linter.RulesRecord = {
  "max-lines": "off",
  "max-lines-per-function": "off",
};

export default defineConfig(
  { ignores: ["dist/**", "build/**", "coverage/**"] },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  {
    linterOptions: { reportUnusedDisableDirectives: "error" },
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      ...boundaryDiscipline,
      ...typeSystemDiscipline,
      ...modelTheDomain,
      ...neverSwallowAFailure,
      ...fixRootCauses,
      ...oneLogger,
      ...minimizeReaderLoad,
      ...subtractBeforeYouAdd,
      "no-restricted-syntax": ["error", parseBodiesWithASchema, handleOrPropagateRejections, logThroughTheLogger],
    },
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    extends: [tseslint.configs.disableTypeChecked],
  },
  {
    files: loggerFiles,
    rules: {
      "no-restricted-globals": "off",
      "no-restricted-syntax": ["error", parseBodiesWithASchema, handleOrPropagateRejections],
    },
  },
  {
    files: testFiles,
    plugins: { vitest },
    rules: {
      ...testBehaviorNotImplementation,
      ...assertionsAllowedInTests,
      ...lengthCapsOnlyInProduction,
      "no-restricted-syntax": [
        "error",
        parseBodiesWithASchema,
        handleOrPropagateRejections,
        logThroughTheLogger,
        mockOnlyWhatYouDontOwn,
      ],
    },
  },
);

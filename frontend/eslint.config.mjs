import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,

  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",

    // Cesium runtime assets are generated/copied from node_modules.
    // They are third-party distribution files and must not be linted.
    "public/cesium/**",
  ]),
]);

export default eslintConfig;

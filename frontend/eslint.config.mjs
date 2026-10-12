import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["src/app/dashboard/page.tsx"],
    rules: {
      // One-shot mount prefetch: a single effect pulls every dashboard
      // section in parallel. The cascade is intentional and bounded.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    files: [
      "src/app/family/page.tsx",
      "src/app/dashboard/page.tsx",
      "src/components/navbar.tsx",
      "src/components/landing/problem-stats.tsx",
      "src/components/family/totp-card.tsx",
    ],
    rules: {
      // These files legitimately set state inside effects — one-shot mount
      // prefetch, route-change nav reset, animated count-up, and TOTP timer.
      // Over-aggressive lint warnings would otherwise block CI.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "off",
    },
  },
]);

export default eslintConfig;

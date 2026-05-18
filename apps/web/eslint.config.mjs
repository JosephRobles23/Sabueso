import coreWebVitals from "eslint-config-next/core-web-vitals"

export default [
  ...coreWebVitals,
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
]

import nextCoreWebVitals from 'eslint-config-next/core-web-vitals'
import nextTypeScript from 'eslint-config-next/typescript'

// ESLint 9 uses flat config, and Next 16 removed the `next lint` command, so
// eslint is invoked directly. eslint-config-next 16 publishes flat config
// arrays, so no compatibility shim is needed.
const config = [
  {
    ignores: ['.next/**', 'node_modules/**', 'coverage/**', 'next-env.d.ts'],
  },
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    // Build tooling is CommonJS and runs in Node, not in the bundle.
    files: ['*.config.js', 'jest.setup.js'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
]

export default config

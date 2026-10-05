// Lets plain Node run the scripts that import the site's TypeScript (src/utils/*.ts), whose own imports
// leave out the ".ts" (Vite resolves them; Node does not). Use with:
//   node --experimental-transform-types --import ./scripts/ts-hook.mjs scripts/<script>.mjs
import { register } from 'node:module'

register(
  'data:text/javascript,' +
    encodeURIComponent(
      "export async function resolve(s, c, next) { try { return await next(s, c) } catch (e) { if (e.code === 'ERR_MODULE_NOT_FOUND' && !/\\.[a-z]+$/.test(s)) return next(s + '.ts', c); throw e } }",
    ),
)

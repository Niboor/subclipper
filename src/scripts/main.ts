export * from "./components/dual-handle-slider"
export * from "./components/closable-dialog"

import { SwapOptions } from "htmx.org";
import "./main.css"

// Restoring a page from htmx's history cache (back/forward) replaces document.body's
// innerHTML wholesale with the cached snapshot, then reprocesses it. Every element in
// that snapshot with hx-trigger="load" - <main>, the video selection dropdown, the file
// browser list, etc. - looks "new" to htmx post-swap and fires again, even though the
// snapshot already has settled, correct content. That redundantly re-fetches everything
// and, worse, opens a fresh SSE connection per re-fetch without closing the old one.
// hx-trigger="load[!window.htmxRestoringHistory()]" on those elements uses this flag to
// skip that redundant refire specifically during a history restore.
//
// This is set up here, at module top-level, rather than inside main() below: htmx's own
// ESM build auto-processes the document on DOMContentLoaded independently of (and
// sometimes before) this module's own async setup finishes, so hx-trigger conditions can
// already be evaluated before main() would otherwise get around to defining this. Plain
// addEventListener (rather than htmx.on) avoids even depending on htmx having loaded yet.
let restoringHistory = false;
(window as any).htmxRestoringHistory = () => restoringHistory;
document.body.addEventListener(`htmx:historyCacheHit`, () => { restoringHistory = true; })
document.body.addEventListener(`htmx:historyRestore`, () => { restoringHistory = false; })

let htmx: typeof import("htmx.org").default;
async function main() {
  const htmxModule = await import('htmx.org');
  htmx = htmxModule.default;

  (window as any).htmx = htmx;
  
  await import("htmx-ext-response-targets")
  await import("htmx-ext-sse")
  
  // Custom HTMX extensions can be defined here
  // Ensure the existing query parameters in the current URL are preserved, only changing those that are requested to be changed
  htmx.defineExtension(`preserve-params`, {
    onEvent: (name, event) => {
        if(name === `htmx:configRequest`) {

            //preserve-params can be false, true, or a specific space-separated list of params that should be preserved
            const preserveParams: string | null = event.detail.elt.getAttribute(`preserve-params`)
            if(preserveParams === `false`) {
              return true
            }

            const removeParamsAttribute: string | null = event.detail.elt.getAttribute(`remove-params`)
            const removeParams = removeParamsAttribute !== null ? removeParamsAttribute.split(` `) : []

            const onlyPreserveTheseParams = (
              preserveParams === null || preserveParams === `true` || preserveParams === `*` || preserveParams === `` || preserveParams.startsWith(`not`)
                ? undefined
                : preserveParams.split(` `)
            )

            // Path that a request is sent to
            const path = event.detail.path.split("?")[0]
            // Query parameters sent to that path
            const params = event.detail.path.split("?")[1] || ""
            const nextSearchParams = new URLSearchParams(params)
            // The query parameters currently in the browser's URL, filtering out the params that should not be preserved
            const currentSearchParams = new URLSearchParams(window.location.search)

            // Remove any params that we explicitly do not want to preserve in the current search params, and who also appears in the nextSearchParams
            currentSearchParams.forEach((value, key) => {
              if(removeParams.includes(key) && nextSearchParams.getAll(key).includes(value)) {
                currentSearchParams.delete(key)
                nextSearchParams.delete(key, value)
              }
            })

            // Remove any params that are not listed in onlyPreserveTheseParams
            if(onlyPreserveTheseParams !== undefined) {
              currentSearchParams.forEach((_, key) => {
                if(!onlyPreserveTheseParams.includes(key)) {
                  currentSearchParams.delete(key)
                }
              })
            }

            // The names of the query parameters, made unique
            const keys = new Set([...currentSearchParams.keys(), ...nextSearchParams.keys()])
            const newSearchParams = new URLSearchParams()
            keys.forEach(key => {
                const searchParams = nextSearchParams.get(key) ?? currentSearchParams.get(key)
                if(searchParams !== null) {
                  newSearchParams.set(key, searchParams)
                }
            })
            event.detail.path = `${path}?${newSearchParams.toString()}`
        }
        return true
    },
  })

  // HTMX uses history.pushState, which does not update CSS :target pseudoclass: https://developer.mozilla.org/en-US/docs/Web/CSS/:target#description
  // Fix taken and modified from https://github.com/bigskysoftware/htmx/issues/3447
  htmx.on(`htmx:afterSwap`, (event: Event & { detail: SwapOptions["eventInfo"] }) => {
    const hashFragment = event.detail.pathInfo?.requestPath.split(`#`).at(1)
    if(hashFragment !== undefined && hashFragment !== ``) {
      window.location.hash = hashFragment;
    }
  })

  htmx.process(document.body)
}
main()

export { htmx }
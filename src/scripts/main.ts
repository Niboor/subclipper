export * from "./components/dual-handle-slider";
import { SwapOptions } from "htmx.org";
import "./main.css"

let htmx: typeof import("htmx.org").default;
async function main() {
  const htmxModule = await import('htmx.org');
  htmx = htmxModule.default;

  (window as any).htmx = htmx;
  
  await import("htmx-ext-response-targets")
  
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

            const onlyPreserveTheseParams = (
              preserveParams === null || preserveParams === `true` || preserveParams === `*` || preserveParams === ``
                ? undefined
                : preserveParams.split(` `)
            )

            // Path that a request is sent to
            const path = event.detail.path.split("?")[0]
            // Query parameters sent to that path
            const params = event.detail.path.split("?")[1] || ""
            const nextSearchParams = new URLSearchParams(params)
            console.log(`nextSearchParams: `, nextSearchParams)
            // The query parameters currently in the browser's URL, filtering out the params that should not be preserved
            const currentSearchParams = new URLSearchParams(window.location.search)
            console.log(`currentSearchParams before: `, currentSearchParams)
            if(onlyPreserveTheseParams !== undefined) {
              currentSearchParams.forEach((_, key) => {
                if(!onlyPreserveTheseParams.includes(key)) {
                  currentSearchParams.delete(key)
                }
              })
            }
            console.log(`currentSearchParams after: `, currentSearchParams)

            // The names of the query parameters, made unique
            const keys = new Set([...currentSearchParams.keys(), ...nextSearchParams.keys()])
            console.log(`keys: `, keys)
            const newSearchParams = new URLSearchParams()
            keys.forEach(key => {
                const searchParams = nextSearchParams.get(key) ?? currentSearchParams.get(key)
                if(searchParams !== null) {
                  newSearchParams.set(key, searchParams)
                }
            })
            console.log(`newSearchParams: `, newSearchParams)
            event.detail.path = `${path}?${newSearchParams.toString()}`
        }
        return true
    },
  })

  // HTMX uses history.pushState, which does not update CSS :target pseudoclass: https://developer.mozilla.org/en-US/docs/Web/CSS/:target#description
  // Fix taken and modified from https://github.com/bigskysoftware/htmx/issues/3447
  htmx.on(`htmx:afterSwap`, (event: Event & { detail: SwapOptions["eventInfo"] }) => {
    const hashFragment = event.detail.pathInfo.requestPath.split(`#`).at(1)
    if(hashFragment !== undefined && hashFragment !== ``) {
      console.log(`updooting hash`)
      window.location.hash = hashFragment;
    }
  })

  htmx.process(document.body)
}
main()

export { htmx }
export * from "./components/dual-handle-slider";
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
            // The query parameters currently in the browser's URL, filtering out the params that should not be preserved
            const currentSearchParams = new URLSearchParams(window.location.search)
            if(onlyPreserveTheseParams !== undefined) {
              currentSearchParams.forEach((_, key) => {
                if(!onlyPreserveTheseParams.includes(key)) {
                  currentSearchParams.delete(key)
                }
              })
            }

            // The names of the query parameters, made unique
            const keys = new Set([...currentSearchParams.keys(), ...nextSearchParams.keys()])
            // All the keys that should be taken from `nextSearchParams` and not from `currentSearchParams`
            const excludeKeys = new Set(new URLSearchParams(event.detail.formData).keys())
            const newSearchParams = new URLSearchParams()
            keys.forEach(key => {
                if(!excludeKeys.has(key)) {
                  const searchParams = nextSearchParams.get(key) ?? currentSearchParams.get(key)
                  if(searchParams !== null) {
                    newSearchParams.set(key, searchParams)
                  }
                }
            })
            event.detail.path = `${path}?${newSearchParams.toString()}`
        }
        return true
    },
  })

  htmx.defineExtension(`copy-to-clipboard`, {
    onEvent: (name, event) => {
        if(name === `htmx:beforeSwap`) {
            const response = event.detail.xhr.response
            const blob = new Blob([response], { type: `image/gif` })
            navigator.clipboard.write([
                new ClipboardItem({
                    [blob.type]: blob
                })
            ])
        }
        return true
    }
  })


  htmx.process(document.body)
}
main()

export { htmx }
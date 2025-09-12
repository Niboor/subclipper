export * from "./components/dual-handle-slider";
import "./main.css"

let htmx: typeof import("htmx.org").default;
async function main() {
  const htmxModule = await import('htmx.org');
  htmx = htmxModule.default;

  (window as any).htmx = htmx;
  
  await import("htmx-ext-response-targets")
  
  htmx.process(document.body)
  
  // Custom HTMX extensions can be defined here
  // Ensure the existing query parameters in the current URL are preserved, only changing those that are requested to be changed
  htmx.defineExtension(`preserve-params`, {
    onEvent: (name, event) => {
        if(name === `htmx:configRequest`) {
            const path = event.detail.path.split("?")[0];
            const params = event.detail.path.split("?")[1] || "";
            const currentSearchParams = new URLSearchParams(window.location.search)
            const nextSearchParams = new URLSearchParams(params);
            const keys = new Set([...currentSearchParams.keys(), ...nextSearchParams.keys()])
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
}
main()

export { htmx }
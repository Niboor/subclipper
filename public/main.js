// Ensure the existing query parameters in the current URL are preserved, only changing those that are requested to be changed
htmx.defineExtension(`preserve-params`, {
    onEvent: (name, event) => {
        if(name === `htmx:configRequest`) {
            const path = event.detail.path.split("?")[0];
            const params = event.detail.path.split("?")[1] || "";
            const currentSearchParams = new URLSearchParams(window.location.search)
            const nextSearchParams = new URLSearchParams(params);
            const keys = new Set([...currentSearchParams.keys(), ...nextSearchParams.keys()])
            const newSearchParams = new URLSearchParams()
            keys.forEach(key => {
                newSearchParams.set(key, nextSearchParams.get(key) ?? currentSearchParams.get(key))
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
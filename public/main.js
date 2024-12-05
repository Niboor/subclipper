// Ensure the existing query parameters in the current URL are preserved, only changing those that are requested to be changed
htmx.defineExtension(`preserve-params`, {
    onEvent: (name, event) => {
        if (name === "htmx:configRequest") {
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
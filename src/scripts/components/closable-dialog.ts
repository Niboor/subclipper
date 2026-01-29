import styles from '../main.css?inline';
import { html, LitElement, unsafeCSS } from "lit";
import { customElement, property } from "lit/decorators.js";
import { createRef, ref, Ref } from 'lit/directives/ref.js';

@customElement("closable-dialog")
export class ClosableDialog extends LitElement {
  static styles = [unsafeCSS(styles)]

  // @property({ type: String })
  // public id: string

  rootRef: Ref<HTMLDialogElement> = createRef()

  @property({ type: Boolean })
  public open: boolean = false

  closeDialog() {
    this.rootRef.value?.close()
    this.rootRef.value?.remove()
  }

  render() {
    return html`
        <dialog
            ${ref(this.rootRef)}
            id=${this.id}
            class="modal"
            ?open=${this.open}
            closedby="any"
        >
          <div
            class="modal-box w-full md:w-fit h-full md:h-fit"
          >
            <form method="dialog">
                <button
                    class="btn btn-lg md:btn-md btn-circle btn-ghost absolute right-2 top-2"
                >
                    ✕
                </button>
            </form>
            <slot></slot>
          </div>
          <form method="dialog" class="modal-backdrop">
              <button>
                  close
              </button>
          </form>
        </dialog>
    `
  }
}
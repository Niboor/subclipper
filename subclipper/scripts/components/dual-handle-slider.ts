import styles from '../main.css?inline';
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from "lit/decorators.js";
import { createRef, ref, Ref } from 'lit/directives/ref.js';

@customElement("dual-handle-slider")
export class DualHandleSlider extends LitElement {
  static styles = [unsafeCSS(styles)]

  sliderTrackRef: Ref<HTMLDivElement> = createRef();

  @property({ type: Number })
  public start: number = 0;
  @property({ type: Number })
  public end: number = 10;
  @property({ type: Number })
  public padding: number = 5;
  @property({ type: Number })
  public step: number = 0.1;
  @property({ type: Number })
  public originalStart: number
  @property({ type: Number })
  public originalEnd: number

  @property({ type: String })
  public startError?: string

  @property({ type: String })
  public endError?: string

  @state()
  private currentStart: number = 0
  @state()
  private currentEnd: number = 0

  @state()
  private sliderStart: number = 0
  @state()
  private sliderEnd: number = 0

  firstUpdated() {
    this.originalStart = this.originalStart ? this.originalStart : this.start
    this.originalEnd = this.originalEnd ? this.originalEnd : this.end
    this.currentStart = this.start;
    this.currentEnd = this.end;
    this.sliderStart = this.originalStart - this.padding;
    this.sliderEnd = this.originalEnd + this.padding;
    this.requestUpdate()
  }

  private timeToPosition(time: number): number {
    const totalRange = this.sliderEnd - this.sliderStart;
    return (time - this.sliderStart) / totalRange;
  }

  private positionToTime(position: number): number {
    const totalRange = this.sliderEnd - this.sliderStart;
    return position * totalRange + this.sliderStart;
  }

  private startDrag(handle: "start" | "end", event: MouseEvent | TouchEvent) {
    event.preventDefault();

    const move = (e: MouseEvent | TouchEvent) => {
      const position = this.getRelativePosition(e);
      const time = this.positionToTime(position);

      if (handle === "start") {
        this.currentStart = Math.min(time, this.currentEnd - this.step)
      } else {
        this.currentEnd = Math.max(time, this.currentStart + this.step)
      }
      this.requestUpdate();
    };

    const stop = () => {
      document.removeEventListener("mousemove", move as any);
      document.removeEventListener("mouseup", stop);
      document.removeEventListener("touchmove", move as any);
      document.removeEventListener("touchend", stop);
    };

    document.addEventListener("mousemove", move as any);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", move as any, { passive: false });
    document.addEventListener("touchend", stop);
  }

  // Percentage of the position that the user selected in relation to the slider track
  private getRelativePosition(e: MouseEvent | TouchEvent): number {

    const track = this.sliderTrackRef.value
    if(track === undefined) {
      return 0
    }

    const rect = track.getBoundingClientRect();
    const clientX = e instanceof MouseEvent ? e.clientX : e.touches[0].clientX
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  }

  private updateFromInput(type: "start" | "end", value: number) {
    if (type === "start") {
      this.currentStart = Math.min(value, this.currentEnd - this.step);
    } else {
      this.currentEnd = Math.max(value, this.currentStart + this.step);
    }
    this.requestUpdate();
  }

  reset() {
    this.currentStart = this.originalStart;
    this.currentEnd = this.originalEnd;
    this.requestUpdate();
  }

  handleFormData({ formData }: FormDataEvent) {
    formData.append(`start`, this.currentStart.toString())
    formData.append(`end`, this.currentEnd.toString())
    formData.append(`original_start`, this.originalStart.toString())
    formData.append(`original_end`, this.originalEnd.toString())
  }

  connectedCallback(): void {
      super.connectedCallback()
      const root = this.getRootNode() as HTMLElement
      const forms = Array.from(root.querySelectorAll(`form`))
      const form = forms.find(form => form.contains(this))
      if(form !== undefined) {
          form.addEventListener(`formdata`, this.handleFormData.bind(this))
      }

  }

  render() {
    const startPos = this.timeToPosition(this.currentStart) * 100;
    const endPos = this.timeToPosition(this.currentEnd) * 100;


    return html`
      <div class="flex flex-row gap-2 items-center">
        <button
            type="button"
            class="btn btn-sm btn-ghost btn-circle"
            @click=${() => this.reset()}
        >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
        </button>
        <div class="relative w-full h-2 rounded">
          <div
            ${ref(this.sliderTrackRef)}
            class="slider-track top-0 left-0 w-full h-3 rounded-full"
            style="background: color-mix(in oklab,currentColor 10%,#0000);"
          ></div>
          <div
             class="slider-range absolute -translate-y-1/4 top-0 h-6 bg-base-content rounded-full"
             style="left:calc(${startPos}% - 1rem); width:calc(${endPos - startPos}% + 2rem);"
          ></div>
  
          <div
            class="slider-handle absolute top-1/2 -translate-y-1/3 -translate-x-1/2 w-4 h-4 bg-base-200 rounded-full shadow cursor-pointer"
            style="left:${startPos}%;"
            @mousedown=${(e: MouseEvent) => this.startDrag("start", e)}
            @touchstart=${(e: TouchEvent) => this.startDrag("start", e)}
          ></div>
  
          <div
            class="slider-handle absolute top-1/2 -translate-y-1/3 -translate-x-1/2 w-4 h-4 bg-base-200 rounded-full shadow cursor-pointer"
            style="left:${endPos}%;"
            @mousedown=${(e: MouseEvent) => this.startDrag("end", e)}
            @touchstart=${(e: TouchEvent) => this.startDrag("end", e)}
          ></div>
        </div>
      </div>

      <div class="flex flex-row justify-between mt-4">
        <fieldset class="flex flex-col gap-1">
          <legend class="fieldset-legend">Start time</legend>
          <label class="input w-30 validator ${this.startError ? `input-error` : ``}">
            <input
              id="startInput"
              type="number"
              step=${this.step}
              value=${this.currentStart.toFixed(2)}
              @change=${(e: Event) =>
                this.updateFromInput(
                  "start",
                  parseFloat((e.target as HTMLInputElement).value)
                )}
            />
            <span class="text-sm">s</span>
          </label>
          ${
            this.startError ? html`<div class="text-error">${this.startError}</div>` : html``
          }
        </fieldset>
        <fieldset class="flex flex-col gap-1">
          <legend class="fieldset-legend">End time</legend>
          <label class="input w-30 validator ${this.endError ? `input-error` : ``}">
            <input
              id="endInput"
              type="number"
              step=${this.step}
              value=${this.currentEnd.toFixed(2)}
              @change=${(e: Event) =>
                this.updateFromInput(
                  "end",
                  parseFloat((e.target as HTMLInputElement).value)
                )}
            />
            <span class="text-sm">s</span>
          </label>
          ${
            this.endError ? html`<div class="text-error">${this.endError}</div>` : html``
          }
        </fieldset>
      </div>
    `
  }
}
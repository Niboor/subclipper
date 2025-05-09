class DualHandleSlider {
    constructor(element, options = {}) {
        // Core properties
        this.element = element;

        // Subtitle timing properties
        this.subtitleStart = options.subtitleStart
        this.subtitleEnd = options.subtitleEnd
        this.currentStart = this.subtitleStart
        this.currentEnd = this.subtitleEnd

        this.padding = options.padding || 5;  // Default 5 second padding
        this.step = options.step || 0.1
        this.decimals = this.step.toString().split(".")[1].length

        // Calculate the total range including padding
        this.sliderStart = this.subtitleStart - this.padding;
        this.sliderEnd = this.subtitleEnd + this.padding;

        // UI elements
        this.track = null;
        this.range = null;
        this.startHandle = null;
        this.endHandle = null;

        // Initialize the slider
        this.init();
    }

    init() {
        // Create slider elements
        this.element.innerHTML = `
            <div class="slider-track"></div>
            <div class="slider-range"></div>
            <div class="slider-handle slider-handle-start"></div>
            <div class="slider-handle slider-handle-end"></div>
        `;

        // Cache DOM elements
        this.track = this.element.querySelector('.slider-track');
        this.range = this.element.querySelector('.slider-range');
        this.startHandle = this.element.querySelector('.slider-handle-start');
        this.endHandle = this.element.querySelector('.slider-handle-end');

        // Add event listeners
        this.startHandle.addEventListener('mousedown', this.handleMouseDown.bind(this, 'start'));
        this.endHandle.addEventListener('mousedown', this.handleMouseDown.bind(this, 'end'));

        // Set initial positions
        this.updateUI();
    }

    // Convert a time value to a slider position (0-1)
    timeToPosition(time) {
        const totalRange = this.sliderEnd - this.sliderStart;
        return (time - this.sliderStart) / totalRange;
    }

    // Convert a slider position (0-1) to a time value
    positionToTime(position) {
        const totalRange = this.sliderEnd - this.sliderStart;
        return (position * totalRange) + this.sliderStart;
    }

    // Get the current mouse position as a value between 0 and 1
    getMousePosition(event) {
        const rect = this.track.getBoundingClientRect();
        return Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    }

    handleMouseDown(handle, event) {
        event.preventDefault();

        const moveHandler = (e) => {
            const position = this.getMousePosition(e);
            const time = this.positionToTime(position);

            // Update the appropriate handle
            if (handle === 'start') {
                this.currentStart = parseFloat(Math.min(time, this.currentEnd - this.step).toFixed(this.decimals));
            } else {
                this.currentEnd = parseFloat(Math.max(time, this.currentStart + this.step).toFixed(this.decimals));
            }

            this.updateUI();
        };

        const upHandler = () => {
            document.removeEventListener('mousemove', moveHandler);
            document.removeEventListener('mouseup', upHandler);
        };

        document.addEventListener('mousemove', moveHandler);
        document.addEventListener('mouseup', upHandler);
    }

    // Update all UI elements based on current time values
    updateUI() {
        // Calculate positions
        const startPosition = this.timeToPosition(this.currentStart);
        const endPosition   = this.timeToPosition(this.currentEnd);

        // Update handles and range
        this.startHandle.style.left = `${startPosition * 100}%`;
        this.endHandle.style.left = `${endPosition * 100}%`;
        this.range.style.left = `${startPosition * 100}%`;
        this.range.style.width = `${(endPosition - startPosition) * 100}%`;

        // Update input fields
        const startInput = this.element.parentElement.querySelector('input[id="startInput"]');
        const endInput = this.element.parentElement.querySelector('input[id="endInput"]');
        if (startInput) startInput.value = this.currentStart.toFixed(this.decimals);
        if (endInput) endInput.value = this.currentEnd.toFixed(this.decimals);

        // Update hidden inputs
        const hiddenStartInput = this.element.parentElement.querySelector('input[name="start"]');
        const hiddenEndInput = this.element.parentElement.querySelector('input[name="end"]');
        if (hiddenStartInput) hiddenStartInput.value = this.currentStart;
        if (hiddenEndInput) hiddenEndInput.value = this.currentEnd;
    }

    reset() {
        this.currentStart = this.subtitleStart;
        this.currentEnd = this.subtitleEnd;
        this.updateUI();
    }
}

// Initialize sliders on page load
function initializeSliders() {
    const sliderElements = document.querySelectorAll('.dual-handle-slider');
    sliderElements.forEach(element => {
        // Skip if already initialized
        if (element.dataset.initialized === 'true') return;

        const subtitleStart = parseFloat(element.dataset.startValue) || 0;
        const subtitleEnd = parseFloat(element.dataset.endValue) || 0;
        const padding = parseFloat(element.dataset.padding) || 5
        const step = parseFloat(element.dataset.step) || 0.1

        const slider = new DualHandleSlider(element, {
            subtitleStart,
            subtitleEnd,
            padding,
            step
        });

        // Store slider instance in a WeakMap to maintain the object reference
        if (!window.sliderInstances) {
            window.sliderInstances = new WeakMap();
        }
        window.sliderInstances.set(element, slider);

        // Mark as initialized
        element.dataset.initialized = 'true';
    });
}

// Reset slider to original values
function resetSlider(fieldset) {
    const sliderElement = fieldset.querySelector('.dual-handle-slider');
    if (sliderElement && window.sliderInstances) {
        const slider = window.sliderInstances.get(sliderElement);
        if (slider) {
            slider.reset();
        }
    }
}

// Update slider from input field
function updateSliderFromInput(input, type) {
    const fieldset = input.closest('fieldset');
    const sliderElement = fieldset.querySelector('.dual-handle-slider');
    if (sliderElement && window.sliderInstances) {
        const slider = window.sliderInstances.get(sliderElement);
        if (slider) {
            const value = parseFloat(input.value);

            if (type === 'start') {
                slider.currentStart = Math.min(value, slider.currentEnd - slider.step);
            } else {
                slider.currentEnd = Math.max(value, slider.currentStart + slider.step);
            }

            slider.updateUI();
        }
    }
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', initializeSliders);

// Initialize on HTMX content swap
document.addEventListener('htmx:afterSwap', initializeSliders);
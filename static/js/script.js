// Placeholder for any custom interactivity
document.addEventListener('DOMContentLoaded', function () {
    // Custom scripts here
});

// Hero section
document.addEventListener('DOMContentLoaded', function () {
    let currentStep = 1;

    // Initially load the first form
    loadFormStep();

    // Function to load the form dynamically based on the step
    function loadFormStep() {
        const form = document.getElementById('dynamic-form');
        const steps = document.querySelectorAll('.step');

        // Remove the "active" class from all steps first
        steps.forEach(step => step.classList.remove('active'));

        // Add the "active" class to the current step
        steps[currentStep - 1].classList.add('active');

        if (currentStep === 1) {
            // First form: Your Info
            form.innerHTML = `
                <input type="text" id="name" name="name" class="form-control" placeholder="Your Name">
                <div class="input-group mb-3">
                    <input type="tel" id="contact" name="contact" class="form-control" placeholder="Your Contact">
                </div>
                <input type="text" id="company" name="company" class="form-control" placeholder="Company Name">
                <input type="email" id="email" name="email" class="form-control" placeholder="Work E-mail">
                <button type="button" class="btn btn-primary btn-block mt-3" onclick="showNextForm()">Continue</button>
            `;

            // Initialize intlTelInput for the contact field
            initializeIntlTelInput();

        } else if (currentStep === 2) {
            // Second form: Your Preference
            form.innerHTML = `
                <input type="number" id="seats" name="seats" class="form-control" placeholder="Seats">
                <input type="text" id="location" name="location" class="form-control" placeholder="Location">
                <input type="text" id="area" name="area" class="form-control" placeholder="Area">
                <input type="text" id="budget" name="budget" class="form-control" placeholder="Budget">
                <button type="button" class="btn btn-primary btn-block mt-3" onclick="showNextForm()">Continue</button>
            `;

        } else if (currentStep === 3) {
            // Final step: Report generation
            form.innerHTML = `
                <p>Thank you for your submission! Your report will be sent to your email and WhatsApp shortly.</p>
            `;
        }
    }

    // Function to initialize intlTelInput for the "Your Contact" field
    function initializeIntlTelInput() {
        var telInput = document.querySelector("#contact");

        // Initialize intlTelInput
        var iti = window.intlTelInput(telInput, {
            initialCountry: "in", // Set India's flag by default
            separateDialCode: false, // If you want the dial code separate
            utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js" // utils script for validation
        });

        // Validate the phone number on blur event
        telInput.addEventListener('blur', function () {
            if (iti.isValidNumber()) {
                // If valid, remove error
                telInput.classList.remove("error");
            } else {
                // If invalid, add error class
                telInput.classList.add("error");
            }
        });

        // Reset errors on keyup
        telInput.addEventListener('keyup', function () {
            telInput.classList.remove("error");
        });
    }

    // Function to move to the next form
    window.showNextForm = function() {
        if (currentStep < 3) {
            currentStep++;
            loadFormStep(); // Load the next form
        }
    };

    // Function to handle step navigation on click
    document.querySelectorAll('.step').forEach((stepElement, index) => {
        stepElement.addEventListener('click', function () {
            currentStep = index + 1; // Set currentStep to the clicked step
            loadFormStep(); // Reload the form
        });
    });
});


// Discover section
function scrollLeft() {
    document.getElementById("cities-wrapper").scrollBy({
        left: -300,
        behavior: "smooth"
    });
}

function scrollRight() {
    document.getElementById("cities-wrapper").scrollBy({
        left: 300,
        behavior: "smooth"
    });
}


// Overall presence
// Initialize the map
document.addEventListener('DOMContentLoaded', function () {
    var map = L.map('india-map').setView([22.5937, 78.9629], 5); // Set to India's latitude, longitude

    // Add tile layer (map style)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Add markers for cities
    var cities = [
        { name: "Delhi", coords: [28.6139, 77.2090], color: "green" },
        { name: "Bangalore", coords: [12.9716, 77.5946], color: "orange" },
        { name: "Mumbai", coords: [19.0760, 72.8777], color: "yellow" },
        { name: "Ahmedabad", coords: [23.0225, 72.5714], color: "blue" },
        { name: "Pune", coords: [18.5204, 73.8567], color: "red" },
        { name: "Hyderabad", coords: [17.3850, 78.4867], color: "pink" }
    ];

    // Loop through cities and add markers
    cities.forEach(function(city) {
        L.circleMarker(city.coords, {
            color: city.color,
            radius: 8,
            fillColor: city.color,
            fillOpacity: 0.7
        }).addTo(map)
        .bindPopup(city.name);
    });

    // Optional: Add zoom control
    L.control.zoom({
        position: 'topright'
    }).addTo(map);
});


// testimonials
// JavaScript to handle the scroll by cards
let currentIndex = 0;
const cards = document.querySelectorAll('.testimonial-card');
const cardWidth = cards[0].offsetWidth + 30; // Include margin in width
const row = document.getElementById('testimonial-row');

function scrollLeft() {
    if (currentIndex > 0) {
        currentIndex--; // Decrease index
        row.style.transform = `translateX(-${currentIndex * cardWidth}px)`;
    }
    checkButtons(); // Update button visibility
}

function scrollRight() {
    if (currentIndex < cards.length - 3) { // Check if there are more than 3 cards left to scroll
        currentIndex++; // Increase index
        row.style.transform = `translateX(-${currentIndex * cardWidth}px)`;
    }
    checkButtons(); // Update button visibility
}

// Disable buttons if no more cards left/right
function checkButtons() {
    const leftBtn = document.querySelector('.scroll-btn.left');
    const rightBtn = document.querySelector('.scroll-btn.right');

    // If at the first card, hide the left button
    if (currentIndex === 0) {
        leftBtn.style.visibility = 'hidden'; // Hide left button
    } else {
        leftBtn.style.visibility = 'visible'; // Show left button
    }

    // If at the last card, hide the right button
    if (currentIndex >= cards.length - 3) {
        rightBtn.style.visibility = 'hidden'; // Hide right button
    } else {
        rightBtn.style.visibility = 'visible'; // Show right button
    }
}

// Initial check on page load
checkButtons();

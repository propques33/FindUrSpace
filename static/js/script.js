// Declare currentStep globally so it can be accessed in all functions
let currentStep = 1;

// Function to load the form based on the current step
function loadFormStep() {
    const form = document.getElementById('dynamic-form');
    const steps = document.querySelectorAll('.step');

    if (!form) {
        console.error("Form element with id 'dynamic-form' not found.");
        return;
    }

    console.log("Loading form for step: " + currentStep);

    // Remove 'active' class from all steps, then add to the current step
    steps.forEach(step => step.classList.remove('active'));
    steps[currentStep - 1].classList.add('active');

    // Step 1: User Info
    if (currentStep === 1) {
        form.innerHTML = `
            <input type="text" id="name" name="name" class="form-control" placeholder="Your Name">
            <div class="input-group mb-3">
                <input type="tel" id="contact" name="contact" class="form-control" placeholder="Your Contact">
            </div>
            <input type="text" id="company" name="company" class="form-control" placeholder="Company Name">
            <input type="email" id="email" name="email" class="form-control" placeholder="Work E-mail">
            <button type="button" class="btn btn-primary btn-block mt-3" onclick="submitUserInfo()">Continue</button>
        `;
        initializeIntlTelInput();
    } 
    // Step 2: User Preferences
    else if (currentStep === 2) {
        form.innerHTML = `
            <div class="form-group mb-3">
                <input type="number" id="seats" name="seats" class="form-control" placeholder="Number of Seats">
            </div>
            <div class="form-group mb-3">
                <select id="location" class="form-select" onchange="fetchMicromarkets()">
                    <option selected disabled>Select Location</option>
                </select>
            </div>
            <div class="form-group mb-3">
                <select id="area" class="form-select">
                    <option selected disabled>Select Micromarket</option>
                </select>
            </div>
            <div class="form-group mb-3">
                <select id="budget" class="form-select">
                    <option selected disabled>Select Budget</option>
                </select>
            </div>
            <button type="button" class="btn btn-primary btn-block mt-3" onclick="submitUserPreferences()">Submit</button>
        `;
        fetchLocations(); // Fetch locations when this step loads
    } 
    // Step 3: Thank You Page
    else if (currentStep === 3) {
        form.innerHTML = `
            <p>Thank you for your submission! Your report will be sent to your email and WhatsApp shortly.</p>
            <button type="button" class="btn btn-secondary btn-block mt-3" onclick="startAgain()">Start Again</button>
        `;
    }
}

// Function to initialize intlTelInput for the "Your Contact" field
function initializeIntlTelInput() {
    var telInput = document.querySelector("#contact");
    var iti = window.intlTelInput(telInput, {
        initialCountry: "in",
        separateDialCode: false,
        utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js"
    });

    telInput.addEventListener('blur', function () {
        if (iti.isValidNumber()) {
            telInput.classList.remove("error");
        } else {
            telInput.classList.add("error");
        }
    });

    telInput.addEventListener('keyup', function () {
        telInput.classList.remove("error");
    });
}

// Function to reset the form and start again
function startAgain() {
    currentStep = 1; 
    loadFormStep(); 
}

// Function to handle form submission for "Your Info"
function submitUserInfo() {
    let name = document.getElementById('name').value;
    let contact = document.getElementById('contact').value;
    let company = document.getElementById('company').value;
    let email = document.getElementById('email').value;

    if (!name || !contact || !company || !email) {
        alert('All fields are required.');
        return;
    }

    fetch('/submit_info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ name, contact, company, email })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success' || data.status === 'exists') {
            currentStep++;
            loadFormStep(); 
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Function to handle form submission for "Your Preference"
function submitUserPreferences() {
    let seats = document.getElementById('seats').value;
    let location = document.getElementById('location').value;
    let area = document.getElementById('area').value;
    let budget = document.getElementById('budget').value;

    if (!seats || !location || !area || !budget) {
        alert('All fields are required.');
        return;
    }

    fetch('/submit_preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ seats, location, area, budget })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            currentStep++;
            loadFormStep(); 
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Fetch unique locations (cities) from the database and make dropdown scrollable
function fetchLocations() {
    console.log('Fetching locations...');
    fetch('/get_locations', {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Locations data:', data); // Debugging info
        const locationDropdown = document.getElementById('location');
        locationDropdown.innerHTML = '<option selected disabled>Select Location</option>';
        
        data.locations.forEach(function(location) {
            let option = document.createElement("option");
            option.value = location;
            option.text = location;
            locationDropdown.appendChild(option);
        });

        // Adjust size of the dropdown on focus
        locationDropdown.addEventListener('focus', function () {
            locationDropdown.size = 5;
        });

        locationDropdown.addEventListener('change', function () {
            closeDropdown('location');
            fetchMicromarkets(); // Fetch micromarkets when location changes
        });
    })
    .catch(error => {
        console.error('Error fetching locations:', error);
    });
}

// Fetch unique micromarkets for the selected city
function fetchMicromarkets() {
    const city = document.getElementById('location').value;
    console.log('Fetching micromarkets for city:', city);

    fetch(`/get_micromarkets?city=${city}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Micromarkets data:', data); // Debugging info
        const areaDropdown = document.getElementById('area');
        areaDropdown.innerHTML = '<option selected disabled>Select Micromarket</option>';
        
        data.micromarkets.forEach(function(micromarket) {
            let option = document.createElement("option");
            option.value = micromarket;
            option.text = micromarket;
            areaDropdown.appendChild(option);
        });

        areaDropdown.addEventListener('focus', function () {
            areaDropdown.size = 5;
        });

        areaDropdown.addEventListener('change', function () {
            closeDropdown('area');
            fetchPrices(); // Fetch prices when micromarket changes
        });
    })
    .catch(error => {
        console.error('Error fetching micromarkets:', error);
    });
}

// Fetch unique prices for the selected city and micromarket
function fetchPrices() {
    const city = document.getElementById('location').value;
    const micromarket = document.getElementById('area').value;
    console.log('Fetching prices for city:', city, 'and micromarket:', micromarket);

    fetch(`/get_prices?city=${city}&micromarket=${micromarket}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Prices data:', data); // Debugging info
        const budgetDropdown = document.getElementById('budget');
        budgetDropdown.innerHTML = '<option selected disabled>Select Budget</option>';
        
        data.prices.forEach(function(price) {
            let option = document.createElement("option");
            option.value = price;
            option.text = price;
            budgetDropdown.appendChild(option);
        });

        budgetDropdown.addEventListener('focus', function () {
            budgetDropdown.size = 5;
        });

        budgetDropdown.addEventListener('change', function () {
            closeDropdown('budget');
        });
    })
    .catch(error => {
        console.error('Error fetching prices:', error);
    });
}

// Close dropdown after selection
function closeDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    dropdown.size = 1; // Close dropdown when an option is selected
}

// Handle dropdown close when clicked outside
document.addEventListener('click', function (event) {
    var dropdowns = document.querySelectorAll('.form-select');
    dropdowns.forEach(function (dropdown) {
        if (!dropdown.contains(event.target)) {
            dropdown.size = 1; // Close dropdown when clicked outside
        }
    });
});

// Trigger the initial form loading when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    loadFormStep(); 
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
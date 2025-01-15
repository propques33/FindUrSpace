// Declare currentStep globally so it can be accessed in all functions
let currentStep = 1;
let requestId = null; // Store the requestId for OTP verification

// Function to load the form based on the current step
function loadFormStep() {
    const form = document.getElementById('dynamic-form');
    const steps = document.querySelectorAll('.step');    
    const termsAndConditionsUrl = document.body.getAttribute('data-terms-url');

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
            <input type="text" id="name" name="name" class="form-control" placeholder="Your Name *" required>
            <div class="input-group mb-3 verifybt">
                <input type="tel" id="contact" name="contact" class="form-control" placeholder="Your Contact *" required>
                <button type="button" id="verify-btn" class="btn btn-secondary" class="verify" style="width: 80px; border-radius:8px; padding:4px 0px; position:absolute; right:10px; background-color:#0c1427; font-size:16px;" onclick="sendOtp()">Verify</button>
            </div>
            <div class="form-group mt-3" id="otp-section" style="display:none; position:relative;">
                <input type="text" id="otpInput" class="form-control mr-4"  placeholder="Enter OTP" required>
                <button type="button" class="btn btn-primary ml-2" style="position:absolute; right:10px; top:6px; width:100px; padding:6px 0px; font-size:16px;" onclick="verifyOtp()">Verify OTP</button>
            </div>
            <input type="text" id="company" name="company" class="form-control" placeholder="Company Name *" required>
            <input type="email" id="email" name="email" class="form-control" placeholder="Work E-mail *" required>
            <div class="form-group mb-3">
                <input type="checkbox" id="accept-terms" name="accept-terms" required>
                <label for="accept-terms">I accept the <a href="http://findurspace.tech/tc" target="_blank">terms and conditions *</a></label>
            </div>
            <button type="button" id="continue-btn" class="btn btn-primary btn-block mt-3" onclick="submitUserInfo()">Continue</button>
        `;
        initializeIntlTelInput();
    } 
    // Step 2: User Preferences
    else // In the loadFormStep function, replace the price input section with this styled version:

    if (currentStep === 2) {
        form.innerHTML = `
            <!-- Inventory Type Dropdown -->
        <div class="form-group mb-3">
            <select id="inventory-type" name="inventory-type" class="form-select" required>
                <option value="" selected disabled>Select Inventory Type</option>
                <option value="coworking space">Coworking Space</option>
                <option value="meeting room">Meeting Room</option>
                <option value="virtual office">Virtual Office</option>
                <option value="dedicated desk">Dedicated Desk</option>
                <option value="private cabin">Private Cabin</option>
                <option value="day pass">Day Pass</option>
                <option value="serviced offices">Serviced Offices</option>
                <option value="conference rooms">Conference Rooms</option>
            </select>
        </div>
        
        <!-- Hear About Us Dropdown -->
        <div class="form-group mb-3">
            <select id="hear-about" name="hear-about" class="form-select" required>
                <option value="" selected disabled>Select Source</option>
                <option value="facebook">Facebook</option>
                <option value="google">Google</option>
                <option value="other">Other</option>
            </select>
        </div>

            <div class="form-group mb-3">
                <select id="seats" name="seats" class="form-select" required>
                    <option value="" selected disabled>Select Number of Seats *</option>
                    <option value="0-5">0-5</option>
                    <option value="5-20">5-20</option>
                    <option value="20-50">20-50</option>
                    <option value="50+">50+</option>
                </select>
            </div>
            <div class="form-group mb-3">
                <select id="location" class="form-select" required onchange="fetchMicromarkets()">
                    <option value="" selected disabled>Select Location *</option>
                </select>
            </div>
            <div class="form-group mb-3">
                <select id="area" class="form-select" required>
                    <option value="" selected disabled>Select Micromarket *</option>
                </select>
            </div>
            <div class="form-group mb-3">
                <select id="budget" name="budget" class="form-select" required>
                    <option value="" selected disabled>Enter Budget Per Seat (₹)  *</option>
                    <option value="0-5000">Rs 0-5000</option>
                    <option value="5000-10000">Rs 5000-10000</option>
                    <option value="10000+">Rs 10000+</option>
                </select>
            </div>
            <button type="button" id="submit-btn" class="btn btn-primary btn-block mt-3" onclick="submitUserPreferences()">Submit</button>
        `;
        fetchLocations();
    }
}

function sendOtp() {
    const contactField = document.getElementById('contact');
    const contact = contactField.value.trim();

    // Validate the contact number
    if (!/^\d{10}$/.test(contact)) {
        alert('Please enter a valid 10-digit contact number.');
        contactField.focus();
        return;
    }

    // Prepend +91 for Indian numbers
    const formattedContact = `+91${contact}`;

    // Send OTP request
    fetch('/send_otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mobile: formattedContact })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            requestId = data.requestId; // Save requestId for verification
            document.getElementById('otp-section').style.display = 'block'; // Show OTP input
            alert('OTP sent successfully. Please check your mobile.');
        } else {
            alert(data.message || 'Failed to send OTP. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error sending OTP:', error);
        alert('An error occurred while sending OTP. Please try again.');
    });
}

function verifyOtp() {
    const otpInput = document.getElementById('otpInput');
    const otp = otpInput.value.trim();

    if (!/^\d{4,6}$/.test(otp)) { // Check for a valid 4-6 digit OTP
        alert('Please enter a valid OTP.');
        otpInput.focus();
        return;
    }

    // Verify OTP request
    fetch('/verify_otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requestId, otp })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('OTP verified successfully!');
            document.getElementById('otp-section').style.display = 'none'; // Hide OTP input
            document.getElementById('contact').disabled = true; // Disable contact input
            document.getElementById('verify-btn').disabled = true; // Disable verify button
        } else {
            alert(data.message || 'Failed to verify OTP. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error verifying OTP:', error);
        alert('An error occurred during OTP verification. Please try again.');
    });
}
    
    // Update the validatePrice function to format the value with the ₹ symbol
    function validatePrice(input) {
        // Remove any non-numeric characters except decimal point
        let value = input.value.replace(/[^\d.]/g, '');
        
        // Ensure only one decimal point
        let parts = value.split('.');
        if (parts.length > 2) {
            value = parts[0] + '.' + parts.slice(1).join('');
        }
        
        // Limit to two decimal places
        if (parts.length > 1) {
            value = parts[0] + '.' + parts[1].slice(0, 2);
        }
        
        // Update input value
        input.value = value;
        
        // Validate if it's a valid number
        if (value !== '' && (!isFinite(value) || value <= 0)) {
            alert('Please enter a valid price (numbers only)');
            input.value = '';
            input.focus();
            return false;
        }
        return true;
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
            alert('Please enter a valid contact number');
        }
    });
}

// Function to handle form submission for "Your Info"
function submitUserInfo() {
    const contactField = document.getElementById('contact');
    if (!contactField.disabled) {
        alert('Please verify your contact number before proceeding.');
        return;
    }

    let name = document.getElementById('name').value;
    let company = document.getElementById('company').value;
    let email = document.getElementById('email').value;
    let acceptTerms = document.getElementById('accept-terms').checked;

    if (!name || !company || !email || !acceptTerms) {
        alert('All fields and terms acceptance are required.');
        return;
    }

    // Validate email format
    if (!email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
        alert('Please enter a valid email address.');
        return;
    }

    fetch('/submit_info', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ name, contact: contactField.value, company, email })
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
    let inventoryType = document.getElementById('inventory-type').value; // New field
    let hearAbout = document.getElementById('hear-about').value; // New field

    if (!seats || !location || !area || !budget|| !inventoryType || !hearAbout) {
        alert('All fields are required.');
        return;
    }

    // Check if a valid micromarket is selected
    if (area === "") {
        alert('Please select a valid Micromarket.');
        document.getElementById('area').focus();
        return;
    }

    // Validate budget
    // Static Budget
    // if (!validatePrice(document.getElementById('budget'))) {
    //     return;
    // }

    fetch('/submit_preferences', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ seats, location, area, budget, 'inventory-type': inventoryType, 
            'hear-about': hearAbout  })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.href = '/thankyou';
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

         // Sort locations alphabetically and capitalize the first letter of each option
         const sortedLocations = data.locations
         .map(location => location.charAt(0).toUpperCase() + location.slice(1))
         .sort();
        
         sortedLocations.forEach(function(location) {
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
        areaDropdown.innerHTML = '<option value="" disabled selected>Select Micromarket *</option>';
        
        // Sort micromarkets alphabetically and capitalize the first letter of each option
        const sortedMicromarkets = data.micromarkets
            .map(micromarket => micromarket.charAt(0).toUpperCase() + micromarket.slice(1))
            .sort();

        sortedMicromarkets.forEach(function(micromarket) {
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
// JavaScript function update:
function fetchPrices() {
    const city = document.getElementById('location').value;
    const micromarket = document.getElementById('area').value;
    console.log('Fetching prices for city:', city, 'and micromarket:', micromarket);

    fetch(`/get_prices?city=${encodeURIComponent(city)}&micromarket=${encodeURIComponent(micromarket)}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Prices data:', data); // Debugging info
        const budgetDropdown = document.getElementById('budget');
        budgetDropdown.innerHTML = '<option selected disabled>Select Budget</option>';
        
        // Sort prices in ascending order
        const sortedPrices = data.prices.sort((a, b) => a - b);
        
        sortedPrices.forEach(function(price) {
            let option = document.createElement("option");
            option.value = price;
            // Format the price with commas and add "₹" symbol
            option.text = `₹${price.toLocaleString('en-IN')} per seat`;
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

// discover section
window.onload = function() {
    setInitialScroll();
};

function setInitialScroll() {
    const wrapper = document.getElementById('cities-wrapper');
    if (wrapper.children.length > 1) {
        const cardWidth = wrapper.children[1].offsetWidth; // Gets the width of the second card
        const scrollAmount = cardWidth; // Scrolls to the second card
        wrapper.scrollTo({
            left: scrollAmount,
            behavior: "smooth"
        });
    }
}

function scrollLeftTrending() {
    document.getElementById("trending-cities-wrapper").scrollBy({
        left: -300,
        behavior: "smooth"
    });
}

function scrollRightTrending() {
    document.getElementById("trending-cities-wrapper").scrollBy({
        left: 300,
        behavior: "smooth"
    });
}



// Overall presence
// Initialize the map
document.addEventListener('DOMContentLoaded', function () {
    var map = L.map('india-map', {
        center: [22.5937, 78.9629], // Latitude and Longitude of India
        zoom: 5,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        touchZoom: false,
        keyboard: false,
        zoomControl: false,
        attributionControl: false,
      });
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Hardcoded cities, their coordinates, and colors
    var cities = [
        { name: "Gurgaon", coords: [28.4595, 77.0266], color: "green" },
        { name: "Bangalore", coords: [12.9716, 77.5946], color: "orange" },
        { name: "Kolkata", coords: [22.5726, 88.3639], color: "yellow" },
        { name: "Mumbai", coords: [19.0760, 72.8777], color: "red" },
        { name: "Lucknow", coords: [26.8467, 80.9462], color: "purple" },
        { name: "Pune", coords: [18.5204, 73.8567], color: "blue" },
        { name: "Hyderabad", coords: [17.3850, 78.4867], color: "pink" },
        { name: "Noida", coords: [28.5355, 77.3910], color: "cyan" },
        { name: "Delhi", coords: [28.6139, 77.2090], color: "brown" },
        { name: "Ghaziabad", coords: [28.6692, 77.4538], color: "lime" },
        { name: "Indore", coords: [22.7196, 75.8577], color: "violet" },
        { name: "Chennai", coords: [13.0827, 80.2707], color: "teal" },
        { name: "Ahmedabad", coords: [23.0225, 72.5714], color: "gold" },
        { name: "Jaipur", coords: [26.9124, 75.7873], color: "salmon" },
        { name: "Kochi", coords: [9.9312, 76.2673], color: "magenta" },
        { name: "Chandigarh", coords: [30.7333, 76.7794], color: "indigo" },
        { name: "Coimbatore", coords: [11.0168, 76.9558], color: "navy" },
        { name: "Goa", coords: [15.2993, 74.1240], color: "olive" },
        { name: "Greater Noida", coords: [28.4744, 77.5030], color: "maroon" }
    ];

    // Loop through the cities and add markers with different colors
    cities.forEach(function(city) {
        L.circleMarker(city.coords, {
            color: city.color,  // Use the city's specific color
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
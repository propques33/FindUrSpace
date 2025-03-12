
// Declare currentStep globally so it can be accessed in all functions
let currentStep = 1;
let OTPlessSignin = null;

// Load OTPless SDK
async function OTPlessSdk() {
    return new Promise((resolve) => {
        if (document.getElementById("otpless-sdk") && OTPlessSignin) return resolve();

        const script = document.createElement("script");
        script.src = "https://otpless.com/v4/headless.js";
        script.id = "otpless-sdk";
        script.setAttribute("data-appid", "DMQXR10UUDL7DTU6326R");  // Replace with OTPless App ID

        script.onload = function () {
            const OTPless = Reflect.get(window, "OTPless");
            OTPlessSignin = new OTPless(() => {}); // Fix for 'callback is not defined'
            resolve();
        };
        document.head.appendChild(script);
    });
}

async function initiateOtp() {
    const contactField = document.getElementById('contact');
    const contact = contactField.value.trim();

    if (!/^\d{10}$/.test(contact)) {
        alert('Please enter a valid 10-digit contact number.');
        contactField.focus();
        return;
    }

    await OTPlessSdk();

    const request = {
        channel: "PHONE",
        phone: contact,
        countryCode: "+91",
        expiry: "60"
    };

    try {
        const response = await OTPlessSignin.initiate(request);
        console.log({ response });

        if (response.success) {
            document.getElementById('otp-section').style.display = 'block';
            alert('OTP sent successfully.');
        } else {
            alert('Failed to send OTP. Please try again.');
        }
    } catch (error) {
        console.error('Error sending OTP:', error);
        alert('An error occurred while sending OTP.');
    }
}

function showLoader() {
    document.querySelector(".spinner").style.display = "flex";
    document.querySelector(".loader-overlay").style.display = "block"; // Show overlay
    document.body.style.overflow = "hidden"; // Disable scrolling
}

function hideLoader() {
    document.querySelector(".spinner").style.display = "none";
    document.querySelector(".loader-overlay").style.display = "none"; // Hide overlay
    document.body.style.overflow = "auto"; // Re-enable scrolling
}

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
            <div class="input-group mb-3 verifybt">
                <input type="tel" id="contact" name="contact" class="form-control" placeholder="Your Contact *" required>
                <button type="button" id="verify-btn" class="btn btn-secondary" class="verify" style="width:auto; border-radius:8px; padding:4px 4px; position:absolute; right:10px; background-color:#0c1427; font-size:16px;" onclick="initiateOtp()">Click to Verify</button>
            </div>
            <div class="form-group mt-3" id="otp-section" style="display:none; position:relative;">
                <input type="text" id="otpInput" class="form-control mr-4"  placeholder="Enter OTP" required>
                <button type="button" class="btn btn-primary ml-2" style="position:absolute; right:10px; top:6px; width:100px; padding:6px 0px; font-size:16px;" onclick="verifyOtp()">Verify OTP</button>
            </div>
            <div id="additional-fields" style="display:none;">
                <input type="text" id="name" name="name" class="form-control" placeholder="Your Name *" required>
                <input type="text" id="company" name="company" class="form-control" placeholder="Company Name *" required>
                <input type="email" id="email" name="email" class="form-control" placeholder="Work E-mail *" required>
            </div>
            <div class="form-group mb-3">
                <input type="checkbox" id="accept-terms" name="accept-terms" required checked disabled>
                <label for="accept-terms">I accept the <a href="http://findurspace.tech/tc" target="_blank">terms and conditions *</a></label>
            </div>
            <input type="hidden" id="latitude" name="latitude">
            <input type="hidden" id="longitude" name="longitude">
            <input type="hidden" id="location" name="location">
            <button type="button" id="continue-btn" class="btn btn-primary btn-block mt-1" style="display:none;" onclick="submitUserInfo()">Login</button>
        `;
        initializeIntlTelInput();
    } 
    // Step 2: User Preferences
    else // In the loadFormStep function, replace the price input section with this styled version:

    if (currentStep === 2) {
        form.innerHTML = `
        
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

            <!-- Dynamic Inventory Type Dropdown -->
            <div class="form-group mb-3">
                <select id="inventory-type" name="inventory-type" class="form-select" required>
                    <option value="" selected disabled>Select Inventory Type</option>
                </select>
            </div>

            <div class="form-group mb-3">
                <select id="budget" name="budget" class="form-select" required>
                    <!-- Static options will be added dynamically -->
                </select>
            </div>
            <button type="button" id="submit-btn" class="btn btn-primary btn-block mt-3" onclick="submitUserPreferences()">Find Spaces</button>
        `;
        fetchLocations();
        fetchPrices();
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

// function verifyOtp() {
//     const otpInput = document.getElementById('otpInput');
//     const otp = otpInput.value.trim();

//     if (!/^\d{4,6}$/.test(otp)) { // Check for a valid 4-6 digit OTP
//         alert('Please enter a valid OTP.');
//         otpInput.focus();
//         return;
//     }

//     // Verify OTP request
//     fetch('/verify_otp', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({ requestId, otp })
//     })
//     .then(response => response.json())
//     .then(data => {
//         if (data.success) {
//             alert('OTP verified successfully!');
//             document.getElementById('otp-section').style.display = 'none'; // Hide OTP input
//             document.getElementById('contact').disabled = true; // Disable contact input
//             document.getElementById('verify-btn').disabled = true; // Disable verify button
//         } else {
//             alert(data.message || 'Failed to verify OTP. Please try again.');
//         }
//     })
//     .catch(error => {
//         console.error('Error verifying OTP:', error);
//         alert('An error occurred during OTP verification. Please try again.');
//     });
// }

async function verifyOtp() {
    const contact = document.getElementById('contact').value.trim();
    const otp = document.getElementById('otpInput').value.trim();

    if (!/^\d{6}$/.test(otp)) {
        alert('Enter a valid 6-digit OTP.');
        return;
    }

    await OTPlessSdk();

    try {
        const response = await OTPlessSignin.verify({
            channel: "PHONE",
            phone: contact,
            otp: otp,
            countryCode: "+91"
        });

        console.log({ response });

        if (response.success) {
            alert('OTP Verified!');
            document.getElementById('contact').disabled = true;
            document.getElementById('verify-btn').disabled = true;
            document.getElementById('otp-section').style.display = 'none';

            // Store OTP verification status in sessionStorage
            sessionStorage.setItem('otp_verified', 'true');

            // Check if user exists in the database
            checkUserExists(contact);
            // **DEBUG**
            console.log("Session Storage OTP Verified:", sessionStorage.getItem('otp_verified'));
        } else {
            alert('OTP verification failed. Please try again.');
        }
    } catch (error) {
        console.error('Error verifying OTP:', error);
        alert('An error occurred during OTP verification.');
    }
}
    
// Function to check if the user exists in the database
function checkUserExists(contact) {
    fetch('/check_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contact })
    })
    .then(response => response.json())
    .then(data => {
        const continueBtn = document.getElementById('continue-btn');
        const additionalFields = document.getElementById('additional-fields');
        
        // Show the continue button
        continueBtn.style.display = 'block';

        if (data.exists) {
             // If user exists, pre-fill details
            document.getElementById('name').value = data.name || '';
            document.getElementById('company').value = data.company || '';
            document.getElementById('email').value = data.email || '';

            // Make fields read-only
            document.getElementById('name').readOnly = true;
            document.getElementById('company').readOnly = true;
            document.getElementById('email').readOnly = true;

            // Show additional fields
            additionalFields.style.display = 'block';

             // If user exists, show Login button
             continueBtn.innerText = 'Login';
             continueBtn.onclick = function() {
                 //  window.location.href = `/outerpage?contact=${encodeURIComponent(contact)}`;
                 currentStep = 2; // Move to step 2
                loadFormStep();
             };
        } else {
            // If user does not exist, show Sign Up button
            continueBtn.innerText = 'Sign Up';
            continueBtn.onclick = submitUserInfo;

            // Show additional fields for user input
            additionalFields.style.display = 'block';

            // Make fields editable
            document.getElementById('name').readOnly = false;
            document.getElementById('company').readOnly = false;
            document.getElementById('email').readOnly = false;
        }
    })
    .catch(error => {
        console.error('Error checking user existence:', error);
        alert('An error occurred. Please try again.');
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
    let continueBtn = document.getElementById('continue-btn');
    let loader = document.querySelector(".spinner");

    if (!name || !company || !email || !acceptTerms) {
        alert('All fields and terms acceptance are required.');
        return;
    }

    // Validate email format
    if (!email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
        alert('Please enter a valid email address.');
        return;
    }

    // Get stored location data
    let latitude = sessionStorage.getItem('latitude') || "";
    let longitude = sessionStorage.getItem('longitude') || "";
    let location = sessionStorage.getItem('location') || "Unknown Location";
    // Hide Continue Button and Show Loader
    showLoader();

    fetch('/submit_info', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ name, contact: contactField.value, company, email, latitude, longitude, location })
    })
    .then(response => response.json())
    .then(data => {
        hideLoader();
        if (data.status === 'exists') {
            currentStep++; // Move to step 2 instead of redirecting
            loadFormStep();
            // window.location.href = '/outerpage';
        } else if (data.status === 'success') {
            currentStep++;
            loadFormStep();
        }  else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        hideLoader(); // Hide loader on error
        alert('An error occurred while submitting your details. Please try again.');
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

    console.log("Submitting Preferences:", { seats, location, area, budget, inventoryType, hearAbout });
    
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
        hideLoader();
        if (data.status === 'success') {
            // Redirect with query parameters for filtering
            console.log("Submission successful:", data);
            // const redirectUrl = `/outerpage?location=${encodeURIComponent(location)}&area=${encodeURIComponent(area)}&inventoryType=${encodeURIComponent(inventoryType)}`;
            const redirectUrl = `/thankyou`;
            window.location.href = redirectUrl;
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        hideLoader(); // Hide loader on error
        alert('An error occurred while submitting your preferences. Please try again.');
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
            fetchInventoryTypes();
            fetchPrices(); // Fetch prices when micromarket changes
        });
    })
    .catch(error => {
        console.error('Error fetching micromarkets:', error);
    });
}

// Fetch unique prices for the selected city and micromarket
// JavaScript function update:
//dynamic budget
// function fetchPrices() {
//     const city = document.getElementById('location').value;
//     const micromarket = document.getElementById('area').value;
//     console.log('Fetching prices for city:', city, 'and micromarket:', micromarket);

//     fetch(`/get_prices?city=${encodeURIComponent(city)}&micromarket=${encodeURIComponent(micromarket)}`, {
//         method: 'GET'
//     })
//     .then(response => response.json())
//     .then(data => {
//         console.log('Prices data:', data); // Debugging info
//         const budgetDropdown = document.getElementById('budget');
//         budgetDropdown.innerHTML = '<option selected disabled>Select Budget</option>';
        
//         // Sort prices in ascending order
//         const sortedPrices = data.prices.sort((a, b) => a - b);
        
//         sortedPrices.forEach(function(price) {
//             let option = document.createElement("option");
//             option.value = price;
//             // Format the price with commas and add "₹" symbol
//             option.text = `₹${price.toLocaleString('en-IN')} per seat`;
//             budgetDropdown.appendChild(option);
//         });

//         budgetDropdown.addEventListener('focus', function () {
//             budgetDropdown.size = 5;
//         });

//         budgetDropdown.addEventListener('change', function () {
//             closeDropdown('budget');
//         });
//     })
//     .catch(error => {
//         console.error('Error fetching prices:', error);
//     });
// }

function fetchInventoryTypes() {
    const city = document.getElementById('location').value;
    const micromarket = document.getElementById('area').value;

    if (!city || !micromarket) {
        return;
    }

    console.log(`Fetching inventory types for ${city}, ${micromarket}`);

    fetch(`/get_inventory_types?city=${encodeURIComponent(city)}&micromarket=${encodeURIComponent(micromarket)}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log("Fetched inventory types:", data);
        const inventoryDropdown = document.getElementById('inventory-type');
        inventoryDropdown.innerHTML = '<option value="" selected disabled>Select Inventory Type</option>';

        if (data.inventory_types.length === 0) {
            console.log("No inventory types found.");
            return;
        }
        
        data.inventory_types.forEach(type => {
            let option = document.createElement("option");
            option.value = type;
            option.text = type;
            inventoryDropdown.appendChild(option);
        });

        inventoryDropdown.addEventListener('focus', function () {
            inventoryDropdown.size = 5;
        });

        inventoryDropdown.addEventListener('change', function () {
            closeDropdown('inventory-type');
        });

    })
    .catch(error => {
        console.error('Error fetching inventory types:', error);
    });
}

function fetchPrices() {
    console.log('Populating budget dropdown with static options...');
    const budgetDropdown = document.getElementById('budget');
    budgetDropdown.innerHTML = `
        <option selected disabled>Select Budget</option>
        <option value="5000-10000">₹5000 - ₹10000</option>
        <option value="10000-15000">₹10000 - ₹15000</option>
        <option value="15000+">₹15000+</option>
    `;

    // Add focus and close dropdown behaviors
    budgetDropdown.addEventListener('focus', function () {
        budgetDropdown.size = 5;
    });

    budgetDropdown.addEventListener('change', function () {
        closeDropdown('budget');
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


document.addEventListener('DOMContentLoaded', function () {
    OTPlessSdk();
    loadFormStep();
    getUserLocation(); // Capture location on page load
});

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function (position) {
                let latitude = position.coords.latitude;
                let longitude = position.coords.longitude;

                // Store in sessionStorage (not DB yet)
                sessionStorage.setItem('latitude', latitude);
                sessionStorage.setItem('longitude', longitude);

                // Reverse Geocode to get location name
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`)
                    .then(response => response.json())
                    .then(data => {
                        let location = data.display_name || "Unknown Location";
                        sessionStorage.setItem('location', location);
                        console.log("User Location Fetched:", location);
                    })
                    .catch(error => console.error('Error fetching location:', error));
            },
            function (error) {
                console.error('Location access denied or unavailable:', error);
                sessionStorage.setItem('location', "Unknown Location");
            }
        );
    } else {
        console.warn('Geolocation not supported.');
        sessionStorage.setItem('location', "Unknown Location");
    }
}



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

// Ensure the loader is hidden by default when the page loads
document.addEventListener('DOMContentLoaded', function () {
    document.querySelector(".spinner").style.display = "none";
});


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
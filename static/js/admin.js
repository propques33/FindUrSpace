document.addEventListener("DOMContentLoaded", function () {

    // Toggle Navbar Minimize
    const navbar = document.getElementById('navbar');
    const toggleBtn = document.getElementById('toggleBtn');
    
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            navbar.classList.toggle('minimized');
            toggleBtn.classList.toggle('minimized');
        });
    }

    // Function to update micromarkets when a city is selected
    const cityDropdown = document.getElementById('city');
    const micromarketDropdown = document.getElementById('micromarket');

    function updateListings() {
        const selectedCity = cityDropdown.value;
        const selectedMicromarket = micromarketDropdown.value;
        const price = document.querySelector('input[name="price"]').value;

        let query = `city=${selectedCity}`;

        if (selectedMicromarket !== "Select Micromarket") {
            query += `&micromarket=${selectedMicromarket}`;
        }

        if (price) {
            query += `&price=${price}`;
        }

        // Redirect to the listings URL with the selected filters
        window.location.href = `/admin/listings?${query}`;
    }

    if (cityDropdown) {
        cityDropdown.addEventListener('change', function () {
            const selectedCity = cityDropdown.value;
            micromarketDropdown.innerHTML = '<option>Select Micromarket</option>';

            if (selectedCity !== "Select City") {
                // Fetch micromarkets for the selected city using AJAX
                fetch(`/admin/get_micromarkets/${selectedCity}`)
                    .then(response => response.json())
                    .then(data => {
                        data.forEach(function (micromarket) {
                            const option = document.createElement('option');
                            option.value = micromarket;
                            option.text = micromarket;
                            micromarketDropdown.appendChild(option);
                        });
                    })
                    .catch(error => console.error('Error:', error));

                // Automatically update the listings for the selected city
                updateListings();
            }
        });
    }

    if (micromarketDropdown) {
        micromarketDropdown.addEventListener('change', function () {
            updateListings(); // Update listings when micromarket changes
        });
    }

    // Function to update leads using AJAX
    function updateLead(lead_id, property_id, field, value) {
        fetch('/admin/update_lead', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                lead_id: lead_id,
                property_id: property_id,
                field: field,
                value: value
            }),
        })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }

    // Event listeners for updating leads dynamically
    document.querySelectorAll('.update-lead').forEach(element => {
        element.addEventListener('change', function () {
            const lead_id = this.getAttribute('data-lead-id');
            const property_id = this.getAttribute('data-property-id');
            const field = this.getAttribute('data-field');
            const value = this.value;
            updateLead(lead_id, property_id, field, value);
        });
    });

    // Function to delete a lead
    document.querySelectorAll('.delete-lead').forEach(element => {
        element.addEventListener('click', function () {
            const lead_id = this.getAttribute('data-lead-id');
            const property_id = this.getAttribute('data-property-id');
            if (confirm("Are you sure you want to delete this lead?")) {
                fetch('/admin/delete_lead', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        lead_id: lead_id,
                        property_id: property_id,
                    }),
                })
                    .then(response => response.json())
                    .then(data => {
                        location.reload(); // Reload the page after successful deletion
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
            }
        });
    });
});

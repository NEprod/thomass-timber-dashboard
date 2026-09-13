document.addEventListener("DOMContentLoaded", function () {
  const thicknessDropdown = document.getElementById("slat_thickness");
  const mouldingDropdown = document.getElementById("moulding_type");

  if (thicknessDropdown && mouldingDropdown) {
    // Load mouldings when thickness changes
    thicknessDropdown.addEventListener("change", function () {
      const selectedThickness = thicknessDropdown.value;

      if (!selectedThickness) return;

      fetch(`/api/mouldings?thickness=${selectedThickness}`)
        .then(response => response.json())
        .then(data => {
          mouldingDropdown.innerHTML = ""; // Clear old options

          if (data.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No mouldings available";
            mouldingDropdown.appendChild(option);
            return;
          }

          data.forEach(label => {
            const option = document.createElement("option");
            option.value = label;
            option.textContent = label;
            mouldingDropdown.appendChild(option);
          });

          // Optional: auto-select first
          mouldingDropdown.value = data[0];
          mouldingDropdown.dispatchEvent(new Event("change"));
        });
    });
  }
});
document.addEventListener("DOMContentLoaded", function () {
  const slatDropdown = document.getElementById("slat_thickness");

  if (slatDropdown) {
    fetch("/api/mdf_thicknesses")
      .then(res => res.json())
      .then(data => {
        slatDropdown.innerHTML = ""; // Clear existing options

        data.forEach(value => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = `${value}mm`;
          slatDropdown.appendChild(option);
        });

        // ✅ Set a default selected value
        const defaultValue = "9";
        if (data.includes(Number(defaultValue))) {
          slatDropdown.value = defaultValue;
          slatDropdown.dispatchEvent(new Event("change"));
        } else if (data.length > 0) {
          slatDropdown.value = data[0];
          slatDropdown.dispatchEvent(new Event("change"));
        }

        slatDropdown.dispatchEvent(new Event("change"));
      });
  }
});
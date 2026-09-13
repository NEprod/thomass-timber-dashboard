document.addEventListener("DOMContentLoaded", function () {
  const squareDadoDropdown = document.getElementById("square_dado");

  if (squareDadoDropdown) {
    fetch("/api/square_dado_options")
      .then(response => response.json())
      .then(data => {
        squareDadoDropdown.innerHTML = ""; // Clear existing options

        data.forEach(value => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = value;
          squareDadoDropdown.appendChild(option);
        });

        // ✅ Optional: select default value if needed
        const defaultValue = "45mm";
        if (data.includes(defaultValue)) {
          squareDadoDropdown.value = defaultValue;
        } else if (data.length > 0) {
          squareDadoDropdown.value = data[0];
        }
      });
  }
});
document.addEventListener("DOMContentLoaded", function () {
  const middleDadoDropdown = document.getElementById("middle_dado");

  if (middleDadoDropdown) {
    fetch("/api/middle_dado_options")
      .then(response => response.json())
      .then(data => {
        middleDadoDropdown.innerHTML = ""; // Clear any existing options

        data.forEach(label => {
          const option = document.createElement("option");
          option.value = label;
          option.textContent = label;
          middleDadoDropdown.appendChild(option);
        });

        // Set default
        if (data.length > 0) {
          middleDadoDropdown.value = data[0];
        }
      });
  }
});
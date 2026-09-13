document.addEventListener("DOMContentLoaded", function () {
  const thicknessDropdown = document.getElementById("slat_thickness");
  const panelTypeDropdown = document.getElementById("panel_type");
  const ledgeDropdown = document.getElementById("ledge_type");

  function updateLedgeOptions() {
    if (!thicknessDropdown || !panelTypeDropdown || !ledgeDropdown) return;

    const thicknessRaw = thicknessDropdown.value;
    const panelType = panelTypeDropdown.value.toLowerCase();

    const thickness = parseInt(thicknessRaw);
    if (isNaN(thickness)) {
      ledgeDropdown.innerHTML = "";
      return;
    }

    let options = [];

    if (panelType.includes("ledge & bead")) {
      const ledge3x = thickness * 3;
      options.push(`${ledge3x}mm ledge (3x Slat thickness) to incorporate bead`);
    } else {
      const ledge2x = thickness * 2;
      options.push(`${ledge2x}mm ledge (2x Slat thickness)`);
    }

    // Clear and populate
    ledgeDropdown.innerHTML = "";
    options.forEach(text => {
      const option = document.createElement("option");
      option.value = text;
      option.textContent = text;
      ledgeDropdown.appendChild(option);
    });

    ledgeDropdown.value = options[0];
    ledgeDropdown.dispatchEvent(new Event("change"));
  }

  // Update on thickness or panel type change
  if (thicknessDropdown && panelTypeDropdown) {
    thicknessDropdown.addEventListener("change", updateLedgeOptions);
    panelTypeDropdown.addEventListener("change", updateLedgeOptions);
    updateLedgeOptions(); // run once on page load

  }
});
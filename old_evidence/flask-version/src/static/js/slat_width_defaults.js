document.addEventListener("DOMContentLoaded", function () {
  const panelTypeDropdown = document.getElementById("panel_type");
  const slatWidthDropdown = document.getElementById("slat_width");

  let slatWidthUserModified = false;

  // If user changes the slat width manually, we remember it
  slatWidthDropdown.addEventListener("change", () => {
    slatWidthUserModified = true;
  });

  panelTypeDropdown.addEventListener("change", () => {
    if (slatWidthUserModified) return;

    const panelType = panelTypeDropdown.value.toLowerCase();

    if (panelType.includes("bead")) {
      slatWidthDropdown.value = "75";
    } else {
      slatWidthDropdown.value = "100";
    }
  });

  // Trigger once on load if needed
  panelTypeDropdown.dispatchEvent(new Event("change"));
});
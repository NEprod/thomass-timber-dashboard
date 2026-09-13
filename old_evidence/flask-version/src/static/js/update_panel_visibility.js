document.addEventListener("DOMContentLoaded", function () {
  const jobTypeDropdown = document.getElementById("job_type");
  const panelTypeDropdown = document.getElementById("panel_type");

  const squareBlock = document.getElementById("square-options");
  const dadoBlock = document.getElementById("dado-options");

  const mouldingGroup = document.getElementById("moulding_group");
  const ledgeGroup = document.getElementById("ledge_group");

  const middleDado = document.getElementById("middle_dado_group");
  const gapWidth = document.getElementById("gap_width_group");
  const squareDado = document.getElementById("square_dado_group");

  function updateVisibility() {
    const jobType = jobTypeDropdown?.value?.toLowerCase() || "";
    const panelType = panelTypeDropdown?.value?.toLowerCase() || "";

    // --- Toggle Square vs Dado block ---
    if (jobType.includes("full") || jobType.includes("half")) {
      squareBlock.style.display = "block";
      dadoBlock.style.display = "none";
    } else if (jobType.includes("dado")) {
      squareBlock.style.display = "none";
      dadoBlock.style.display = "block";
    }

    // --- Toggle Square fields ---
    if (mouldingGroup && ledgeGroup) {
      if (panelType.includes("ledge") && panelType.includes("bead")) {
        mouldingGroup.style.display = "block";
        ledgeGroup.style.display = "block";
      } else if (panelType.includes("ledge")) {
        mouldingGroup.style.display = "none";
        ledgeGroup.style.display = "block";
      } else if (panelType.includes("bead")) {
        mouldingGroup.style.display = "block";
        ledgeGroup.style.display = "none";
      } else {
        mouldingGroup.style.display = "none";
        ledgeGroup.style.display = "none";
      }
    }

        // --- Toggle Dado layout ---
    if (gapWidth && squareDado && middleDado) {
        if (panelType === "dado") {
            gapWidth.classList.add("d-none");
            squareDado.classList.add("d-none");

            middleDado.classList.remove("col-6");
            middleDado.classList.add("col-12");
        } else {
            gapWidth.classList.remove("d-none");
            squareDado.classList.remove("d-none");

            middleDado.classList.remove("col-12");
            middleDado.classList.add("col-6");
        }
    }
  }

  // Recheck on dropdown change
  if (jobTypeDropdown && panelTypeDropdown) {
    jobTypeDropdown.addEventListener("change", updateVisibility);
    panelTypeDropdown.addEventListener("change", updateVisibility);

    // Trigger once on load
    updateVisibility();
  }
});
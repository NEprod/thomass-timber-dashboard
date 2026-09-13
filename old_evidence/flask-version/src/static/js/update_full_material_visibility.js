function updateBeadVisibility() {
  const panelType = document.getElementById("panel_type")?.value.toLowerCase() || "";
  const showBeadFields = panelType.includes("bead") || panelType.includes("ledge");

  document.querySelectorAll(".bead-only").forEach(el => {
    if (showBeadFields) {
      el.classList.remove("d-none");
    } else {
      el.classList.add("d-none");

      // Optional: Clear values if hiding
      const inputs = el.querySelectorAll("input");
      inputs.forEach(input => input.value = "");
    }
  });
}

// Call on load and on change
document.addEventListener("DOMContentLoaded", updateBeadVisibility);
document.getElementById("panel_type")?.addEventListener("change", updateBeadVisibility);
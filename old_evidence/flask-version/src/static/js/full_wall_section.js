document.addEventListener("DOMContentLoaded", function () {
  const container = document.getElementById("full-wall-sections");
  const addBtn = document.getElementById("add-wall-section");
  const removeBtn = document.getElementById("remove-wall-section");
  const template = document.getElementById("full-wall-section-template");

  function renumberWallSections() {
    const sections = document.querySelectorAll(".wall-section");
    sections.forEach((section, index) => {
      section.dataset.index = index + 1;
      const title = section.querySelector(".section-title .section-number");
      if (title) title.textContent = index + 1;
    });

    // Update remove button
    removeBtn.style.display = sections.length > 1 ? "inline-block" : "none";
  }

  function addSection() {
    const clone = document.importNode(template.content, true);

    const wrapper = document.createElement("div");
    wrapper.className = "wall-section border p-3 rounded mb-3";
    container.appendChild(wrapper);
    wrapper.appendChild(clone);

    renumberWallSections();
  }

  function removeSection() {
    const sections = document.querySelectorAll(".wall-section");
    if (sections.length > 1) {
      container.removeChild(sections[sections.length - 1]);
      renumberWallSections();
      if (window.triggerMaterialTotalsFullWall) {
        window.triggerMaterialTotalsFullWall();
      }
    }
  }

  function updateBeadGroups() {
    const panelType = document.getElementById("panel_type")?.value || "";
    const hasBead = panelType.toLowerCase().includes("bead");

    document.querySelectorAll(".wall-section").forEach(section => {
      const beadGroup = section.querySelector(".bead-group");
      if (beadGroup) {
        if (hasBead) {
          beadGroup.classList.remove("d-none");
        } else {
          beadGroup.classList.add("d-none");
          // Optionally clear value
          const beadInput = beadGroup.querySelector("input[name='bead_strips']");
          if (beadInput) beadInput.value = "";
        }
      }
    });
  }

  // Run on load (in case panel type is already set)
  updateBeadGroups();

  // Run whenever panel type changes
  const panelTypeSelector = document.getElementById("panel_type");
  if (panelTypeSelector) {
    panelTypeSelector.addEventListener("change", updateBeadGroups);
  }

  // On load: insert the first section
  addSection();

  // Button bindings
  addBtn?.addEventListener("click", addSection);
  removeBtn?.addEventListener("click", removeSection);
});
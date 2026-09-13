document.addEventListener("DOMContentLoaded", function () {
  console.log("[full_wall_calc.js] Loaded and running...");

  function inputsAreFilled(wrapper) {
    const length = wrapper.querySelector("input[name='wall_length']").value;
    const height = wrapper.querySelector("input[name='wall_height']").value;
    const horz = wrapper.querySelector("input[name='horz_squares']").value;
    const vert = wrapper.querySelector("input[name='vert_squares']").value;
    const slat = document.getElementById("slat_width")?.value || "";
    const fullDays = document.getElementById("full_days")?.value || "";
    const extraHours = document.getElementById("extra_hours")?.value || "";

    const labourEntered = (Number(fullDays) > 0) || (Number(extraHours) > 0);

    return length && height && horz && vert && slat && labourEntered;
  }

  document.getElementById("panel_type")?.addEventListener("change", () => {
    document.querySelectorAll(".wall-section").forEach(wrapper => {
      if (inputsAreFilled(wrapper)) {
        triggerCalculation(wrapper);
      }
    });
  });

  const slatWidthInput = document.getElementById("slat_width");
  if (slatWidthInput) {
    slatWidthInput.addEventListener("input", () => {
      document.querySelectorAll(".wall-section").forEach(wrapper => {
        if (inputsAreFilled(wrapper)) {
          triggerCalculation(wrapper);
        }
      });
    });
  }

  ["full_days", "extra_hours"].forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener("input", () => {
        document.querySelectorAll(".wall-section").forEach(wrapper => {
          if (inputsAreFilled(wrapper)) {
            triggerCalculation(wrapper);
          } else {
          // Clear output if any required field is now missing
          wrapper.querySelector("input[name='square_width']").value = "";
          wrapper.querySelector("input[name='square_height']").value = "";
          wrapper.querySelector("input[name='horz_strips']").value = "";
          wrapper.querySelector("input[name='vert_strips']").value = "";
          wrapper.querySelector("input[name='horz_pieces_per_strip']").value = "";
          wrapper.querySelector("input[name='bead_strips']").value = "";

            // Clear Material Totals fields
            [
              "total_hv_strips",
              "boards_needed",
              "linear_meterage_panelling",
              "linear_meterage_beading",
              "board_cost",
              "bead_cost",
              "mastic_needed",
              "mastic_cost",
              "cut_cost",
              "delivery_cost"
            ].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.value = "";
            });

            // Clear Job Totals fields
            [
              "material_cost",
              "labour_cost",
              "take_home",
              "final_price"
            ].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.value = "";
            });
          }
        });
      });
    }
  });

  async function triggerCalculation(wrapper) {
    const sectionId = wrapper.dataset.index || "unknown";

    const wall_width = Number(wrapper.querySelector("input[name='wall_length']").value);
    const wall_height = Number(wrapper.querySelector("input[name='wall_height']").value);
    const horz_squares = Number(wrapper.querySelector("input[name='horz_squares']").value);
    const vert_squares = Number(wrapper.querySelector("input[name='vert_squares']").value);
    const slat_thickness = Number(document.getElementById("slat_thickness")?.value || 0);
    const slat_width = Number(document.getElementById("slat_width")?.value || 0);
    const panel_type = document.getElementById("panel_type")?.value || "";
    const moulding_type = document.getElementById("moulding_type")?.value || "";

    if (!(wall_width && wall_height && horz_squares && vert_squares && slat_width)) return;

    try {
      // --- Fetch board_length ---
      const boardRes = await fetch(`/api/board_length?thickness=${slat_thickness}`);
      const boardData = await boardRes.json();
      const board_length = boardData?.[0] || 5440;

      // --- Fetch kerf ---
      const kerfRes = await fetch(`/api/get_kerf`);
      const kerfData = await kerfRes.json();
      const kerf = kerfData?.[0] || 30;

      // --- Conditionally fetch bead_length ---
      let bead_length = null;
      if (panel_type.toLowerCase().includes("bead") || panel_type.toLowerCase().includes("ledge")) {
        const beadRes = await fetch(`/api/bead_length?moulding_type=${moulding_type}`);
        const beadData = await beadRes.json();
        bead_length = beadData?.[0] || 5440;
      }

      const payload = {
        section_id: sectionId,
        wall_width,
        wall_height,
        horz_squares,
        vert_squares,
        slat_width,
        board_length,
        kerf,
        bead_length,
        panel_type
      };

      console.log(`[Wall ${sectionId}] Sending data to API:`, payload);

      const calcRes = await fetch("/api/calculate/full_wall", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await calcRes.json();
      console.log(`[Wall ${sectionId}] [Calc Result]:`, data);
      if (!window.allWallCutData) window.allWallCutData = {};
      window.allWallCutData[sectionId] = data;

      // --- Populate fields ---
      wrapper.querySelector("input[name='square_width']").value = data.square_width || "";
      wrapper.querySelector("input[name='square_height']").value = data.square_height || "";
      wrapper.querySelector("input[name='horz_strips']").value = data.horz_strips || "";
      wrapper.querySelector("input[name='vert_strips']").value = data.vert_strips || "";
      wrapper.querySelector("input[name='horz_pieces_per_strip']").value = data.horz_pieces_per_strip || "";
      wrapper.querySelector("input[name='bead_strips']").value = data.bead_strips || "";

      if (window.triggerMaterialTotalsFullWall) {
        window.triggerMaterialTotalsFullWall();
      }

    } catch (err) {
      console.error(`[Wall ${sectionId}] [Calc Error]:`, err);
    }
  }

  function watchInputs(wrapper) {
    console.log("[watchInputs] Hooked to:", wrapper);

    const monitoredInputs = wrapper.querySelectorAll(
      "input[name='wall_length'], input[name='wall_height'], input[name='horz_squares'], input[name='vert_squares']"
    );

    monitoredInputs.forEach(input => {
      input.addEventListener("input", () => {
        console.log("[input change] Value changed on:", input.name, "→", input.value);
        if (inputsAreFilled(wrapper)) {
          console.log("[input change] All values filled, triggering calculation.");
          triggerCalculation(wrapper);
        } else {
            console.log("[input change] Waiting for all inputs to be filled...");

            wrapper.querySelector("input[name='square_width']").value = "";
            wrapper.querySelector("input[name='square_height']").value = "";
            wrapper.querySelector("input[name='horz_strips']").value = "";
            wrapper.querySelector("input[name='vert_strips']").value = "";
            wrapper.querySelector("input[name='horz_pieces_per_strip']").value = "";
            wrapper.querySelector("input[name='bead_strips']").value = "";

            // Clear Material Totals fields
            [
              "total_hv_strips",
              "boards_needed",
              "linear_meterage_panelling",
              "linear_meterage_beading",
              "board_cost",
              "bead_cost",
              "mastic_needed",
              "mastic_cost",
              "cut_cost",
              "delivery_cost"
            ].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.value = "";
            });

            // Clear Job Totals fields
            [
              "material_cost",
              "labour_cost",
              "take_home",
              "final_price"
            ].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.value = "";
            });
        }
      });
    });
  }

  // Delay slightly to ensure DOM is ready
  setTimeout(() => {
    const wrappers = document.querySelectorAll(".wall-section");
    console.log("[Init] Hooked up inputs for", wrappers.length, "sections");
    wrappers.forEach(watchInputs);
  }, 100);

  // Also watch new sections added dynamically
  const addButton = document.getElementById("add-wall-section");
  if (addButton) {
    addButton.addEventListener("click", () => {
      setTimeout(() => {
        const wrappers = document.querySelectorAll(".wall-section");
        const latest = wrappers[wrappers.length - 1];
        watchInputs(latest);
      }, 50);
    });
  }
});
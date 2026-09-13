console.log("[full_wall_material_totals.js] Loaded");

window.triggerMaterialTotalsFullWall = async function () {
  console.log("[Material Totals] Triggered for full wall");

  // Example: fetch values from the DOM
  const slatThickness = Number(document.getElementById("slat_thickness")?.value || 0);
  const slatWidth = Number(document.getElementById("slat_width")?.value || 0);
  const mouldingType = document.getElementById("moulding_type")?.value || "";

  // Collect all square_strip_cut_list data from DOM
  const sections = [];
  document.querySelectorAll(".wall-section").forEach(wrapper => {
    const vertStrips = Number(wrapper.querySelector("input[name='vert_strips']")?.value || 0);
    const horzStrips = Number(wrapper.querySelector("input[name='horz_strips']")?.value || 0);
    const beadStrips = Number(wrapper.querySelector("input[name='bead_strips']")?.value || 0);

    sections.push({
      square_strip_cut_list: {
        vertical: Array(vertStrips).fill({ used: 1000 }),
        horizontal: Array(horzStrips).fill({ used: 1000 }),
      },
      bead_cut_list: {
        square_beads: Array(beadStrips).fill({ used: 1000 })
      }
    });
  });

  try {
    const [beadLengthRes, boardLengthRes, boardWidthRes, kerfRes, boardPriceRes, beadPriceRes, masticPriceRes, cutPriceRes, deliveryRes, masticCoverageRes] = await Promise.all([
      fetch(`/api/bead_length?moulding_type=${mouldingType}`),
      fetch(`/api/board_length?thickness=${slatThickness}`),
      fetch(`/api/board_width?thickness=${slatThickness}`),
      fetch(`/api/get_kerf`),
      fetch(`/api/board_price?thickness=${slatThickness}`),
      fetch(`/api/bead_price?moulding_type=${mouldingType}`),
      fetch(`/api/mastic_price`),
      fetch(`/api/cut_price`),
      fetch(`/api/delivery_cost`),
      fetch(`/api/mastic_coverage`)
    ]);

    const beadLength = (await beadLengthRes.json())[0] || 5440;
    const boardLength = (await boardLengthRes.json())[0] || 5440;
    const boardWidth = (await boardWidthRes.json())[0] || 5440;
    const kerf = (await kerfRes.json())[0] || 30;
    const boardPrice = (await boardPriceRes.json())[0] || 50;
    const beadPrice = (await beadPriceRes.json())[0] || 40;
    const masticPrice = (await masticPriceRes.json())[0] || 40;
    const cutPrice = (await cutPriceRes.json())[0] || 40;
    const deliveryCost = (await deliveryRes.json())[0] || 50;
    const masticCoverage = (await masticCoverageRes.json())[0] || 60;

    const payload = {
      sections,
      slat_thickness: slatThickness,
      slat_width: slatWidth,
      ledge_width: slatWidth * 2,
      bead_length: beadLength,
      board_length: boardLength,
      board_width: boardWidth,
      kerf,
      board_cost_each: boardPrice,
      bead_cost_each: beadPrice,
      mastic_unit_price: masticPrice,
      cut_cost_per_strip: cutPrice,
      delivery_cost: deliveryCost,
      mastic_linear_coverage: masticCoverage
    };

    const res = await fetch("/api/material_totals/full_wall", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    console.log("[Material Totals] Result:", data);
    window.latestMaterialTotals = data;

    // Populate values
    document.getElementById("total_hv_strips").value = data.total_hv_strips || "";
    document.getElementById("boards_needed").value = data.boards_needed || "";
    document.getElementById("board_cost").value = `£${data.board_cost?.toFixed(2) || "0.00"}`;
    document.getElementById("beads_needed").value = data.beads_needed || "";
    document.getElementById("bead_cost").value = `£${data.bead_cost?.toFixed(2) || "0.00"}`;
    document.getElementById("linear_meterage_panelling").value = `${data.linear_meterage_panelling || 0}m`;
    document.getElementById("linear_meterage_beading").value = `${data.linear_meterage_beading_ledge || 0}m`;
    document.getElementById("mastic_needed").value = data.mastic_needed || "";
    document.getElementById("mastic_cost").value = `£${data.mastic_cost?.toFixed(2) || "0.00"}`;
    document.getElementById("cut_cost").value = `£${data.cut_cost?.toFixed(2) || "0.00"}`;
    document.getElementById("delivery_cost").value = `£${data.delivery_cost?.toFixed(2) || "0.00"}`;

    if (window.triggerJobTotalsCalculation) {
      window.triggerJobTotalsCalculation();
    }

  } catch (err) {
    console.error("[Material Totals] Error calculating totals:", err);
  }
};
document.addEventListener("DOMContentLoaded", function () {
  console.log("[job_totals.js] Loaded and ready.");

  async function triggerJobTotalsCalculation() {
    console.log("[Job Totals] Triggered");

    const panelType = document.getElementById("panel_type")?.value || "";

    // --- Parse inputs safely ---
    const getVal = (id) => parseFloat(document.getElementById(id)?.value.replace("£", "").replace("m", "").trim() || 0);

    const panelling_lm = getVal("linear_meterage_panelling");
    const bead_ledge_lm = (panelType.toLowerCase().includes("bead") || panelType.toLowerCase().includes("ledge"))
      ? getVal("linear_meterage_beading")
      : 0;

    const board_cost = getVal("board_cost");
    const bead_cost = getVal("bead_cost");
    const mastic_cost = getVal("mastic_cost");
    const cut_cost = getVal("cut_cost");
    const delivery_cost = getVal("delivery_cost");

    const full_days = parseFloat(document.getElementById("full_days")?.value || 0);
    const extra_hours = parseFloat(document.getElementById("extra_hours")?.value || 0);

    try {
      const [
        mdfRes,
        beadRes,
        dayRes,
        hourRes
      ] = await Promise.all([
        fetch("/api/mdf_slat_per_m"),
        fetch("/api/bead_per_m"),
        fetch("/api/day_rate"),
        fetch("/api/hourly_rate")
      ]);

      const mdf_slat_rate = parseFloat((await mdfRes.json())?.[0] || 0);
      const bead_ledge_rate = parseFloat((await beadRes.json())?.[0] || 0);
      const day_rate = parseFloat((await dayRes.json())?.[0] || 0);
      const hourly_rate = parseFloat((await hourRes.json())?.[0] || 0);

      const payload = {
        board_cost,
        bead_cost,
        mastic_cost,
        cut_cost,
        delivery_cost,
        panelling_lm,
        bead_ledge_lm,
        full_days,
        extra_hours,
        mdf_slat_rate,
        bead_ledge_rate,
        day_rate,
        hourly_rate
      };

      const res = await fetch("/api/job_totals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      // Check for backend error
      if (data.error) {
        console.error("[Job Totals] API Error:", data.error);
        return;
      }

      // --- Update fields ---
      document.getElementById("material_cost").value = `£${data.material_cost.toFixed(2)}`;
      document.getElementById("labour_cost").value = `£${data.labour_cost.toFixed(2)}`;
      document.getElementById("take_home").value = `£${data.take_home.toFixed(2)}`;
      document.getElementById("final_price").value = `£${data.final_price.toFixed(2)}`;

    } catch (err) {
      console.error("[Job Totals] Error calculating:", err);
    }
  }

  // Global trigger (can be called after any relevant update)
  window.triggerJobTotalsCalculation = triggerJobTotalsCalculation;

});
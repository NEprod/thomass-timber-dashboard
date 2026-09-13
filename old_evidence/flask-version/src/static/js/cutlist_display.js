document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("generate_cutlist");
  const display = document.getElementById("cutlist_display");

  function toTitleCase(str) {
    return str
      .toLowerCase()
      .replace(/\b\w/g, char => char.toUpperCase());
  }

  if (button && display) {
    button.addEventListener("click", () => {
      const wallSections = window.allWallCutData || {};
      const materialData = window.latestMaterialTotals || {};
      let output = "";

      // Loop through all wall sections
      for (const [sectionId, wallData] of Object.entries(wallSections)) {
        output += `[MDF Strips Cut List] Wall Section ${sectionId}\n`;

        // --- MDF STRIPS ---
        const strips = wallData.square_strip_cut_list || {};
        output += "[MDF Strips Layout]\n";
        for (const direction of ["vertical", "horizontal"]) {
          const group = strips[direction] || {};
          const stripNames = Object.keys(group).sort((a, b) => {
            const numA = parseInt(a.match(/\d+/)?.[0] || "0", 10);
            const numB = parseInt(b.match(/\d+/)?.[0] || "0", 10);
            return numA - numB;
          });
          output += `  [${toTitleCase(direction)} Strips (${stripNames.length} total)]:\n`;
          for (const strip of stripNames) {
            const cuts = group[strip]?.cuts?.join(", ") || "";
            const used = (group[strip]?.used ?? 0).toFixed(1);
            output += `    ${strip}: [${cuts}] | Used: ${used}mm\n`;
          }
        }

        // --- Bead Cuts ---
        const beadList = wallData.bead_cut_list || {};
        const beadGroups = Object.entries(beadList);
        if (beadGroups.length) {
          output += `[Bead Strips Layout]:\n`;
          for (const [groupName, strips] of beadGroups) {
            const names = Object.keys(strips).sort((a, b) => {
              const numA = parseInt(a.match(/\d+/)?.[0] || "0", 10);
              const numB = parseInt(b.match(/\d+/)?.[0] || "0", 10);
              return numA - numB;
            });
            output += `  [${toTitleCase(groupName.replace(/_/g, " "))} (${names.length}):]\n`;
            for (const name of names) {
              const cuts = strips[name]?.cuts?.join(", ") || "";
              const used = (strips[name]?.used ?? 0).toFixed(1);
              output += `    ${name}: [${cuts}] | Used: ${used}mm\n`;
            }
          }
        }

        output += "\n"; // Space between sections
      }

      // --- BOARD SUMMARY (Global, not per section) ---
      const boards = materialData.board_cut_summary?.boards || [];
      output += `[Board Cut Layout (${boards.length} boards)]:\n`;
      boards.forEach((board, idx) => {
        const cuts = board?.cuts?.join(", ") || "";
        const used = board?.used ?? 0;
        output += `  Board ${idx + 1}: [${cuts}] | Used: ${used}mm\n`;
      });

      display.textContent = output.trim() || "No cut list available yet.";
    });
  }
});
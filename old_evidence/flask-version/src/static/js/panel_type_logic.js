document.addEventListener("DOMContentLoaded", function () {
    const jobType = document.getElementById("job_type");
    const panelType = document.getElementById("panel_type");
    const panelBlock = document.getElementById("panel-type-container");

    const panelOptionsByJob = {
        "Full Square Wall": ["Square Panelling", "Square Panelling with Bead"],
        "Half Square Wall": [
            "Half Wall",
            "Half Wall with Bead",
            "Half Wall with Ledge",
            "Half Wall with Ledge & Bead"
        ],
        "Dado Rail": [
            "Dado",
            "Dado Squares Top & Bottom",
            "Dado Double Squares Top & Bottom",
            "Dado Squares Bottom",
            "Dado Double Squares Bottom"
        ]
    };

    function updatePanelOptions(selectedJob) {
        const options = panelOptionsByJob[selectedJob] || [];
        panelType.innerHTML = "";

        if (options.length > 0) {
            panelBlock.style.display = "block";
            options.forEach(opt => {
                const option = document.createElement("option");
                option.value = opt;
                option.textContent = opt;
                panelType.appendChild(option);
            });
        } else {
            panelBlock.style.display = "none";
        }
    }

    if (jobType) {
        jobType.addEventListener("change", e => updatePanelOptions(e.target.value));
        updatePanelOptions(jobType.value); // Initial trigger
    }
});
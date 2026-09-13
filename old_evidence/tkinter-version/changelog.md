## 1.1.1 - 2025-05-28
**Improved**
- Cleaned up residual logic and inline comments in preparation for modular restructure
- Refactored minor GUI labels and variables for clarity and future separation

**Fixed**
- Removed redundant calculations now replaced by cut list length logic
- Ensured consistency across strip count values between logic and display

**Completed**
- JSON-based config for kerf, prices, and materials

**Pending**
- Save/load functionality for full measurement sessions
- Advanced stair panel logic
- Support for multiple dado-style job types
- Full modular restructure of GUI and logic components

## 1.1.0 - 2025-05-28
**Added**
- Full cut list display in GUI for each wall section, including MDF strips and bead cuts
- Shared board cut layout logic to minimize waste across slats and ledges
- Board usage summary with kerf and width taken into account
- Summary display of total boards and strip packing per board
- Integration with existing GUI to display formatted board and strip cut lists

**Improved**
- Dynamic cut list handling based on job type and section data
- Clearer formatting in output panel for workshop-ready display

**Completed**
- Cost calculation summary including mastic, cutting, delivery, labour, and final price

**Pending**
- Save/load functionality for full measurement sessions
- Advanced stair panel logic
- JSON-based config for kerf, prices, and materials

## 1.0.0 - 2025-05-25
**Added**
- Square panelling UI with tkinter including wall dimension, square count, and material fields
- Panelling type dropdown with dynamic visibility for vertical pieces, ledge, and bead fields
- Full vs half wall calculation logic (strip and piece calculations)
- Ledge and bead strip calculations with support for moulding JSON lookup
- Add Wall Section button to support multiple wall inputs
- Section-by-section storage using structured dictionaries
- Material/moulding data loading from JSON

**Pending**
- Cut optimization logic to reduce material waste (shared strips per wall)
- Cut list and batching for workshop-friendly output
- Section spacing and titling for improved UI clarity
- Save/load functionality for measurement sessions


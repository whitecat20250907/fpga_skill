"""CD8 source selection for the optional FPGA input inspector.

Only the BASIC context uses this inspector. A live trajectory owns its original
card immediately. The selected FPGA tensor is displayed as a gray thumbnail;
this control never changes inference input or application interaction.
"""
def control_word(state, selection="off", now_ns=0):
    if state.get("context") != "BASIC":
        return 0
    if state.get("writing", {}).get("state", "IDLE") != "IDLE":
        return 0
    if selection == "cycle":
        mode = (now_ns // 3_000_000_000) % 3
    else:
        mode = {"shared": 0, "face": 1, "palm": 2}.get(selection)
    return 0 if mode is None else 1 | (mode << 1)
